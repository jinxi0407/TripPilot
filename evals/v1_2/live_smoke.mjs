/** Opt-in real Qwen/Amap browser acceptance; run only after the full benchmark. */
import {chromium} from '../../frontend/node_modules/playwright/index.mjs'
import {writeFile} from 'node:fs/promises'

if (!process.argv.includes('--allow-live')) throw new Error('Explicit --allow-live required')
const browser = await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--no-sandbox']})
const report = {provider_mode:'live',rail:'dataset',flight:'dataset',console_errors:0,page_errors:0,http_errors:[],cases:[],map_checks:[]}
const page = await browser.newPage({viewport:{width:1440,height:1100}})
page.on('console',message=>{if(message.type()==='error') report.console_errors++})
page.on('pageerror',()=>report.page_errors++)
page.on('response',response=>{
  if(response.status()>=400){const url=new URL(response.url());report.http_errors.push({host:url.hostname,path:url.pathname,status:response.status()})}
})
const api = page.request
const root = 'http://127.0.0.1:5173'
let originalPreferences
async function jsonRequest(path,data){
  const response = data===undefined ? await api.get(root+path) : await api.post(root+path,{data})
  if(!response.ok()) throw new Error('local_api_failure')
  return response.json()
}
async function reset(){
  await page.goto(root)
  await page.getByLabel('运行模式').selectOption('live')
}
async function submit(query){
  await page.getByLabel('告诉 TripPilot 你的旅行想法').fill(query)
  await page.getByLabel('出发日期').fill('2026-10-10')
  await page.getByRole('button',{name:'生成我的旅行计划',exact:true}).click()
}
async function runCase(id,action,checks){
  const row={id,passed:false,checks:{},reason:null}
  let done
  const listener=async response=>{
    if(!new URL(response.url()).pathname.startsWith('/api/v1/plans/') || response.request().method()!=='GET') return
    try{const body=await response.json();if(!['queued','running'].includes(body.status))done=body}catch{}
  }
  page.on('response',listener)
  const started=Date.now()
  try{
    await action()
    console.log(JSON.stringify({id,started:true}))
    for(let second=0;second<240&&!done;second++)await page.waitForTimeout(1000)
    if(done?.status==='needs_clarification' && id==='memory'){
      row.clarification_assumption='南京同城游；通过正常澄清表单补充出发地/目的地，日期不变'
      if(done.questions.includes('出发城市'))await page.getByLabel('补充出发城市').fill('南京')
      if(done.questions.includes('目的地'))await page.getByLabel('补充目的地').fill('南京')
      if(done.questions.includes('出行天数'))await page.getByLabel('补充天数').fill('3')
      done=undefined
      await page.getByRole('button',{name:'补充并继续'}).click()
      for(let second=0;second<210&&!done;second++)await page.waitForTimeout(1000)
    }
    if(!done) throw new Error('workflow_timeout')
    await writeFile(`docs/v12-live-${id}.json`,JSON.stringify(done,null,2)+'\n')
    const runtime=done.runtime_status, providers=done.provider_status
    row.status=done.status
    row.providers=providers
    row.runtime=runtime
    row.metrics=done.metrics
    row.critic_failure_summaries=done.trace.filter(event=>event.agent==='Critic' && event.status==='failed').map(event=>event.summary)
    row.high_issues=(done.validation?.issues??[]).filter(issue=>issue.severity==='high').map(issue=>issue.type)
    row.checks={
      qwen_live:providers?.qwen?.state==='LIVE' && providers.qwen.model==='qwen-plus',
      amap_live:providers?.amap?.state==='LIVE',
      hotel_live:providers?.hotel?.state==='LIVE',
      hotel_provenance:done.accommodation?.length>0 && done.accommodation.every(a=>a.candidates.length>0 && a.candidates.every(h=>h.source==='amap_live'&&h.realtime_price===null&&h.availability_status==='unknown')),
      mcp_live:runtime?.mcp?.state==='CONNECTED' && runtime.mcp.tools.length===7,
      a2a_local:runtime?.a2a?.local==='ONLINE',
      a2a_transport:done.constraints.destinations.every(city=>city===done.constraints.origin) || runtime?.a2a?.transport==='ONLINE',
      harness_active:runtime?.harness?.state==='ACTIVE',
      memory_active:runtime?.memory?.state==='ACTIVE',
      itinerary:!!done.itinerary && !done.error && !['failed','cancelled'].includes(done.status),
      ...checks(done),
    }
    row.passed=Object.values(row.checks).every(Boolean)
    row.reason=row.passed?null:Object.keys(row.checks).filter(key=>!row.checks[key]).join(',')
    await page.waitForTimeout(1500)
    await page.screenshot({path:`docs/screenshots/v12-live-${id}.png`,fullPage:true})
  }catch(error){row.reason=['workflow_timeout','local_api_failure'].includes(error.message)?error.message:'browser_action_failure'}
  finally{
    page.off('response',listener)
    row.latency_seconds=(Date.now()-started)/1000
    report.cases.push(row)
    await writeFile('evals/v1_2/live_smoke_results.json',JSON.stringify(report,null,2)+'\n')
    console.log(JSON.stringify({id,passed:row.passed,status:row.status,reason:row.reason}))
  }
  return done
}
async function mapCheck(run,day){
  const row={day,passed:false}
  try{
    await page.getByRole('tab',{name:new RegExp(`Day ${day}`)}).click()
    await page.locator('.live-map[data-map-state="live"]').waitFor({timeout:25000})
    await page.waitForTimeout(1800)
    row.expected=run.itinerary.days[day-1].activities.filter(a=>a.poi.coordinates).map((a,i)=>`${i+1}. ${a.poi.name}`)
    row.labels=await page.locator('.amap-poi-label').allTextContents()
    row.within_view=await page.locator('.live-map').evaluate(element=>{
      const box=element.getBoundingClientRect()
      return [...element.querySelectorAll('.amap-poi-label')].every(label=>{const b=label.getBoundingClientRect();return b.width>0&&b.left>=box.left&&b.right<=box.right&&b.top>=box.top&&b.bottom<=box.bottom})
    })
    row.passed=JSON.stringify(row.expected)===JSON.stringify(row.labels)&&row.labels.length>0&&row.within_view
    await page.locator('.map-card').screenshot({path:`docs/screenshots/v12-live-map-day${day}.png`})
  }catch{row.reason='map_verification_failed'}
  report.map_checks.push(row)
}
try{
  originalPreferences=(await jsonRequest('/api/v1/preferences')).preferences
  await jsonRequest('/api/v1/preferences/clear',{})
  await reset()
  const normal=await runCase('normal',()=>page.getByRole('button',{name:/三城慢游/}).click(),run=>({
    five_days:run.itinerary?.days.length===5,critic_pass:run.validation?.valid===true,
    three_hotel_cities:new Set(run.accommodation?.map(a=>a.city)).size===3,
    rail_dataset:run.provider_status.rail.state==='DATASET',flight_dataset:run.provider_status.flight.state==='DATASET',
  }))
  if(normal?.itinerary){for(const day of [1,3,5])await mapCheck(normal,day)}
  await runCase('rain',()=>page.getByRole('button',{name:'模拟暴雨 · 重规划'}).click(),run=>({
    simulated_explicit:run.simulated_rain===true,critic_pass:run.validation?.valid===true,
    replanned:run.metrics.replanning_count>0,
    indoors:run.itinerary?.days.every(day=>day.activities.every(activity=>activity.poi.environment==='indoor')),
  }))
  await runCase('budget',async()=>{
    await page.getByLabel('调整总预算').fill('200')
    await page.getByRole('button',{name:'重新规划',exact:true}).click()
  },run=>({conflict:run.status==='conflict',budget_issue:run.validation?.issues.some(i=>i.type==='BUDGET_EXCEEDED'),replanning_attempt:run.metrics.replanning_count>0}))
  const saved=await jsonRequest('/api/v1/preferences',{query:'我喜欢历史景点和夜景，不喜欢早起，旅行节奏慢一点，住宿最好靠近地铁。',remember_preferences:true})
  report.preference_save=saved.saved===true
  await reset()
  await runCase('memory',()=>submit('帮我规划南京三天，预算3000元。'),run=>({
    loaded:run.memory.long_term_loaded===true,
    preferences:run.constraints.travel_pace==='relaxed' && run.constraints.avoid_early_departure===true && ['历史','夜景'].every(v=>run.constraints.preferences.includes(v)) && run.constraints.accommodation_preferences.includes('near_metro'),
    safe_trace:run.trace.some(event=>event.summary==='已加载旅行偏好'),
    three_days:run.itinerary?.days.length===3,
    critic_pass:run.validation?.valid===true,
  }))
  await jsonRequest('/api/v1/preferences/clear',{})
  await reset()
  await runCase('transport',()=>submit('我想从北京出发去上海玩三天，预算4000元，喜欢历史景点。请比较高铁和飞机的门到门时间，并推荐住宿区域。'),run=>({
    comparison:run.transport_comparisons?.some(c=>['rail','flight'].every(mode=>c.candidates.some(v=>v.mode===mode))),
    datasets:run.transport_comparisons?.every(c=>c.candidates.every(v=>v.provider_mode==='DATASET')),
    consistent_totals:run.transport_comparisons?.every(c=>c.candidates.every(v=>v.estimate.estimated_total_minutes===v.estimate.local_access_minutes+v.estimate.recommended_buffer_minutes+v.estimate.scheduled_duration_minutes+v.estimate.arrival_transfer_minutes)),
    critic_pass:run.validation?.valid===true,
  }))
  report.health=(await jsonRequest('/health')).runtime_status
  report.provider_labels=await page.locator('.provider-indicators').innerText()
  report.runtime_labels=await page.locator('.runtime-indicators').innerText()
}catch{report.setup_error='live_smoke_setup_or_action_failed';process.exitCode=1}
finally{
  if(originalPreferences){
    try{await jsonRequest('/api/v1/preferences/clear',{});await jsonRequest('/api/v1/preferences',{preferences:originalPreferences,remember_preferences:true});report.preferences_restored=true}catch{report.preferences_restored=false}
  }
  const rainCase=report.cases.find(row=>row.id==='rain')
  report.rain_trigger_audit={observed_critic_failure_summaries:rainCase?.critic_failure_summaries??[],weather_specific_critic_chain_demonstrated:rainCase?.critic_failure_summaries?.some(summary=>summary.includes('天气冲突')||summary.includes('WEATHER_RISK'))??false,interpretation:'5/5是集成与场景结果验收；通用replanning_count不能单独证明天气触发Critic路径。'}
  report.success_count=report.cases.filter(row=>row.passed).length
  report.executed=report.cases.length
  report.passed=report.success_count===5 && report.map_checks.length===3 && report.map_checks.every(row=>row.passed) && report.console_errors===0 && report.page_errors===0
  await writeFile('evals/v1_2/live_smoke_results.json',JSON.stringify(report,null,2)+'\n')
  console.log(JSON.stringify({live_smoke_success:report.success_count,executed:report.executed,map_pass:report.map_checks.filter(row=>row.passed).length,console_errors:report.console_errors,page_errors:report.page_errors}))
  if(!report.passed)process.exitCode=1
  await browser.close()
}
