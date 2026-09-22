import {test,expect,type Page} from '@playwright/test'

test.beforeEach(async({page})=>{
 await page.route('**/api/map/config',r=>r.fulfill({json:{configured:false,missing:['VITE_AMAP_SECURITY_CODE'],service_host:'/_AMapService'}}))
 await page.route('https://**/*',r=>r.abort())
 await page.route('**/api/v1/preferences',r=>r.fulfill({json:{preferences:{travel_pace:'relaxed',interests:['history','night_view'],avoid_early_departure:true,accommodation_preferences:['near_metro']}}}))
})
async function generate(page:Page){
 await page.goto('/')
 await page.getByText('数据与运行设置',{exact:true}).click()
 await page.getByLabel('运行模式').selectOption('fixture')
 await page.getByRole('button',{name:/三城慢游/}).click()
 await expect(page.getByRole('tab')).toHaveCount(5)
}
test('旅行模式默认简洁、偏好 chips、摘要与模式切换不发起规划',async({page})=>{
 let posts=0
 page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/plan'))posts++})
 await generate(page)
 await expect(page.getByRole('button',{name:'旅行模式',exact:true})).toHaveAttribute('aria-pressed','true')
 await expect(page.getByLabel('协议与运行状态')).toHaveCount(0)
 await expect(page.locator('.preference-chips')).toContainText('慢节奏')
 await expect(page.locator('.preference-chips')).toContainText('避免早班')
 await expect(page.getByLabel('旅行摘要')).toContainText('上海 → 杭州 → 南京 → 苏州')
 await expect(page.getByLabel('旅行摘要')).toContainText('预算 ¥4,000')
 const before=posts
 await page.getByRole('button',{name:'演示模式',exact:true}).click()
 await expect(page.getByLabel('协议与运行状态')).toBeVisible()
 await page.getByRole('button',{name:'旅行模式',exact:true}).click()
 expect(posts).toBe(before)
})
test('天气工具契约：Day Card 显示传入的真实来源预报，不生成温度',async({page})=>{
 await page.route('**/api/v1/plans/*',async r=>{
  const res=await r.fetch(),data=await res.json()
  // Controlled contract fixture, not a claim of an external LIVE browser call.
  for(const d of data.itinerary?.days??[])d.weather={city:d.city,forecast_date:d.date,status:'live',source:'amap_live',weather_condition:'晴',min_temperature:18,max_temperature:26,precipitation_probability:20}
  await r.fulfill({json:data})
 })
 await generate(page)
 const weather=page.getByLabel('当日天气',{exact:true})
 await expect(weather).toContainText('晴')
 await expect(weather).toContainText('18–26°C')
 await expect(weather).toContainText('降雨概率 20%')
 expect((await weather.boundingBox())!.height).toBeLessThan(100)
 await expect(page.getByLabel('天气概览')).toContainText('杭州')
 await expect(page.getByText('Amap Weather · LIVE · MCP get_weather')).toHaveCount(0)
 await page.getByRole('button',{name:'演示模式',exact:true}).click()
 await expect(page.getByText('Amap Weather · LIVE · MCP get_weather')).toBeVisible()
})
for(const invalid of ['missing','wrong-date','simulated'])test(`无可靠 forecast 不显示伪造温度：${invalid}`,async({page})=>{
 await page.route('**/api/v1/plans/*',async r=>{
  const res=await r.fetch(),data=await res.json()
  for(const d of data.itinerary?.days??[])d.weather=invalid==='missing'?null:{city:d.city,forecast_date:invalid==='wrong-date'?'2099-01-01':d.date,status:invalid==='simulated'?'simulated':'live',source:'amap_live',weather_condition:'晴',min_temperature:88,max_temperature:99}
  await r.fulfill({json:data})
 })
 await generate(page)
 await expect(page.getByLabel('当日天气',{exact:true})).toContainText('天气待临近出发确认')
 await expect(page.getByLabel('当日天气',{exact:true})).not.toContainText('88')
 await expect(page.getByLabel('当日天气',{exact:true})).not.toContainText('99')
 await expect(page.getByLabel('天气概览')).toContainText('杭州 待确认')
})
test('天气冲突提示复用 Critic，室内活动不重复警告',async({page})=>{
 await page.route('**/api/v1/plans/*',async r=>{
  const res=await r.fetch(),data=await res.json()
  if(data.validation)data.validation.issues.push({type:'WEATHER_CONFLICT',severity:'error',status:'confirmed',blocking:true,day:1,message:'天气冲突',suggestion:'室内替换'})
  await r.fulfill({json:data})
 })
 await generate(page)
 await expect(page.locator('.activity-timeline').getByText('天气可能影响该活动')).toHaveCount(1)
})
test('Day Card 全量活动、详情默认折叠、移动端排版可读',async({page})=>{
 let activityCounts:number[]=[]
 page.on('response',async response=>{if(/\/api\/v1\/plans\/[^/]+$/.test(new URL(response.url()).pathname)){const d=await response.json();if(d.itinerary)activityCounts=d.itinerary.days.map((day:{activities:unknown[]})=>day.activities.length)}})
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.name));page.on('console',m=>{if(m.type()==='error')errors.push('console error')})
 await generate(page)
 for(const n of [1,2,3]){
  await page.getByRole('tab',{name:new RegExp(`Day ${n}`)}).click()
  await expect(page.locator('.activity-timeline .activity')).toHaveCount(activityCounts[n-1])
  expect(activityCounts[n-1]).toBeGreaterThanOrEqual(n===2?2:1)
 }
 const details=page.locator('.route-details')
 await expect(details).not.toHaveAttribute('open','')
 await details.locator('summary').click()
 await expect(details).toHaveAttribute('open','')
 await page.setViewportSize({width:390,height:844})
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
 expect(await page.locator('.itinerary-panel').evaluate(el=>getComputedStyle(el).order)).toBe('0')
 expect(await page.locator('.request-panel').evaluate(el=>getComputedStyle(el).order)).toBe('2')
 expect(await page.locator('.activity-title h3').first().evaluate(el=>parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(17)
 expect(errors).toEqual([])
})
test('真实 missing_fields 决定澄清输入，不依赖 questions 文案',async({page})=>{
 await page.route('**/api/v1/plans/*',async r=>{
  const res=await r.fetch(),data=await res.json()
  if(data.status==='needs_clarification')data.questions=['请确认此次旅行的起始时间。']
  await r.fulfill({json:data})
 })
 await page.goto('/')
 await page.getByText('数据与运行设置',{exact:true}).click()
 await page.getByLabel('运行模式').selectOption('fixture')
 await page.getByRole('button',{name:'生成我的旅行计划'}).click()
 await expect(page.getByText('还差一点信息')).toBeVisible()
 await expect(page.getByText('请确认此次旅行的起始时间。')).toBeVisible()
 await page.getByLabel('出发日期').fill('2026-10-10')
 await page.getByRole('button',{name:'补充并继续'}).click()
 await expect(page.getByRole('tab')).toHaveCount(5)
})
