import {useState} from 'react'
import {TrainFront,CloudRain,RefreshCw,Compass} from 'lucide-react'
import type {Run,Itinerary,Day} from '../api/types'
import {money,clock,categoryText} from '../api/client'
import {ProductCards} from './ProductCards'
import {DayWeather,WeatherOverview} from './DayWeather'
import {ValidationSummary,DayValidation,blockingIssues} from './ValidationSummary'
interface Props{run:Run|null;itinerary:Itinerary|null;busy:boolean;selected:number;demoMode?:boolean;onSelect:(day:number)=>void;onRevise:(reason:string,budget?:number)=>void}
const period=(value:string)=>Number(value.slice(11,13))>=18?'晚上':Number(value.slice(11,13))>=12?'下午':'上午'
function DayCard({day,run,demoMode}:{day:Day;run:Run|null;demoMode:boolean}){
 const source=(id:string)=>{const e=run?.evidence.find(e=>e.id===id);return e?.source_kind==='live'?'实时来源':e?.source_kind==='dataset'?'DATASET':'模拟数据'}
 const risky=run?.validation?.issues.some(i=>i.day===day.day&&i.type==='WEATHER_CONFLICT'&&i.blocking)
 const accommodation=run?.accommodation?.find(a=>a.days.includes(day.day))
 const events=[...day.activities.map((a,i)=>({time:a.start,activity:a,index:i})),...(day.breaks??[]).map(b=>({time:b.start,rest:b}))].sort((a,b)=>a.time.localeCompare(b.time))
 return <article className="day-card">
  <div className="day-header"><div><span className="section-kicker">{day.date}</span><h2>Day {day.day} · {day.city}</h2><p className="day-theme">{day.origin_city!==day.city?`${day.origin_city} → ${day.city} · 抵达与探索`:'留一点时间，慢慢认识这座城'}</p></div><span className="day-price">{money(day.estimated_cost)}<small>当日预计</small></span></div>
  <DayWeather day={day} demoMode={demoMode}/>
  {day.rail&&<div className="travel-transfer"><strong>🚄 高铁 · {day.rail.direct?'直达':'中转'}</strong>{day.rail.legs.map((l,i)=><p key={i}>{clock(l.departure_time)} {l.origin_station.name} → {clock(l.arrival_time)} {l.destination_station.name}</p>)}<small>{source(day.rail.legs[0].evidence_id)} · 车次与余票请临行核对</small></div>}
  {day.flight&&<div className="travel-transfer"><strong>✈ 航班</strong><p>{clock(day.flight.departure_time)} {day.flight.origin_airport.name} → {clock(day.flight.arrival_time)} {day.flight.destination_airport.name}</p><small>{day.flight.provider_mode} · 库存未确认</small></div>}
  <div className="activity-timeline">{events.map(event=>{
   if('rest' in event)return <div className="meal-break" key={event.rest.label}><span>{clock(event.rest.start)}–{clock(event.rest.end)}</span>{event.rest.label}</div>
   const a=event.activity;return <div className="activity" key={`${a.poi.id}-${event.index}`}>
    <div className="activity-time"><span>{period(a.start)}</span>{clock(a.start)}<small>{clock(a.end)}</small></div><div className="timeline-node">{event.index+1}</div>
    <div className="activity-info"><div className="activity-title"><h3>{a.poi.name}</h3>{a.poi.environment==='indoor'&&<span className="poi-type">室内</span>}</div>
     <p>预计 {(a.estimated_duration??Math.round((Date.parse(a.end)-Date.parse(a.start))/60000))/60}h{a.optional?' · 可选夜游':''}</p>
     {a.travel_minutes!=null&&<p className="activity-transit">↳ 上一站至此约 {a.travel_minutes} 分钟</p>}
     {risky&&a.poi.environment!=='indoor'&&<p className="weather-warning">天气可能影响该活动</p>}
    </div>
   </div>
  })}</div>
  <div className="day-facts"><span>🚇 当日交通约 {day.local_legs.reduce((s,l)=>s+l.route.duration,0)} min</span>{accommodation&&<span>🏨 {accommodation.recommended_area}</span>}</div>
  <details className="route-details"><summary>查看详细交通与安排</summary><div>{day.local_legs.map((l,i)=><p key={i}><span>{l.route.origin.name} → {l.route.destination.name}<small>{l.route.distance} 米 · {source(l.route.evidence_id)}</small></span><strong>{l.route.duration} min</strong></p>)}{day.activities.map((a,i)=><p key={i}><span>{a.poi.name}<small>{a.poi.tags.join(' · ')} · {source(a.poi.evidence_id)}{a.poi.coordinates?` · ${a.poi.coordinates.longitude.toFixed(4)}, ${a.poi.coordinates.latitude.toFixed(4)}`:''}</small></span><span>门票 {money(a.poi.ticket_price)}</span></p>)}{day.notes?.map((n,i)=><p key={i}>{n}</p>)}</div></details>
  <DayValidation run={run} day={day.day}/>
  <details className="cost-details"><summary>查看当日费用明细</summary>{day.costs.map(c=><p key={c.id}><span>{categoryText[c.category]} · {c.label}</span><strong>{money(c.amount)}</strong></p>)}</details>
 </article>
}
export function ItineraryPanel({run,itinerary,busy,selected,demoMode=false,onSelect,onRevise}:Props){
 const [newBudget,setNewBudget]=useState(4000)
 const blocking=blockingIssues(run?.validation?.issues??[])
 const budgetConflict=blocking.some(i=>i.type==='BUDGET_EXCEEDED')
 const routeConflict=blocking.some(i=>/ROUTE|TRANSPORT|TRANSFER|LOCAL_DURATION|TRAVEL|TRANSIT/.test(i.type))
 const cities=itinerary?[...new Set(itinerary.days.map(d=>d.city))]:[]
 const progress=[['Supervisor','正在理解你的旅行需求…'],['Rail Search','正在查询城际交通…'],['Local Travel','正在搜索目的地与住宿…'],['Travel Planner','正在组合每日活动…'],['Critic','正在检查时间、预算和路线…']]
 return <main className="itinerary-panel">
  <div className="section-heading"><div><span className="section-kicker">A LITTLE PLANNING. A LOT OF DISCOVERY.</span><h1>让每一步，都刚刚好<span>。</span></h1><p className="muted">交通、天气与预算，一起安排妥当。</p></div></div>
  {busy&&<div className="planning-progress" aria-label="规划进度">{progress.map(([agent,label])=>{const event=run?.trace.filter(t=>t.agent===agent||(agent==='Local Travel'&&t.agent==='Amap POI')).at(-1);return <p key={agent} className={event?.status??'pending'}>{event?.status==='succeeded'?'✓':event?.status==='running'?'●':'○'} {label}</p>})}</div>}
  {!itinerary?<div className="empty-plan"><Compass size={48}/><h2>{busy?'你的旅程，正在成形':run?.status==='failed'?'这次规划暂未完成':run?.status==='needs_clarification'?'补充必要信息后即可继续':'好旅程，从一个想法开始'}</h2><p>{run?.status==='needs_clarification'?'左侧已列出需要补充的字段，填写后会继续当前规划。':'写下想去的地方，或试试左侧的江南慢游。把零散想法，变成有据可查的旅行计划。'}</p></div>:<>
   <section className="trip-overview" aria-label="旅行摘要"><div className="overview-top"><span className="section-kicker">你的旅行计划</span><span className="version">版本 {itinerary.version} {busy?'· 正在生成新版':''}</span></div>
    <h2>{[run?.constraints?.origin??itinerary.days[0]?.origin_city,...cities].filter((v,i,a)=>i===0||v!==a[i-1]).join(' → ')}</h2>
    <div className="trip-meta"><span>{itinerary.days.length} 天</span><span>预算 {money(itinerary.costs.budget)}</span><span>{cities.length} 座目的城市</span><span>主要交通：{itinerary.days.some(d=>d.flight)?(itinerary.days.some(d=>d.rail)?'高铁 / 航班':'航班'):(itinerary.days.some(d=>d.rail)?'高铁':'市内交通')}</span><span>旅行节奏：{{relaxed:'舒缓',compact:'紧凑',balanced:'适中'}[run?.constraints?.travel_pace??'balanced']}</span></div>
    <WeatherOverview itinerary={itinerary}/>
   </section>
   <ValidationSummary run={run} demoMode={demoMode}/>
   <div className="day-tabs" role="tablist" aria-label="选择行程日期">{itinerary.days.map(d=><button role="tab" aria-selected={selected===d.day} key={d.day} className={selected===d.day?'selected':''} onClick={()=>onSelect(d.day)}>Day {d.day}<span>{d.city}</span></button>)}</div>
   {itinerary.days.filter(d=>d.day===selected).map(day=><DayCard key={day.day} day={day} run={run} demoMode={demoMode}/>)}
   <ProductCards run={run} selected={selected}/>
   {demoMode&&<div className="replan-bar"><div><RefreshCw size={18}/><strong>演示场景</strong></div><button disabled={busy} onClick={()=>onRevise('weather')}><CloudRain size={15}/>模拟暴雨 · 重规划</button><button disabled={busy} onClick={()=>onRevise('transport')}><TrainFront size={15}/>更新交通</button></div>}
   {budgetConflict&&<div className="budget-update"><label htmlFor="budget">调整总预算</label><span>¥</span><input id="budget" type="number" min="0" value={newBudget} onChange={e=>setNewBudget(Number(e.target.value))}/><button disabled={busy} onClick={()=>onRevise('budget',newBudget*100)}>重新规划</button></div>}
   {routeConflict&&<div className="replan-bar"><button disabled={busy} onClick={()=>onRevise('route')}>重新检查路线</button>{!budgetConflict&&<button disabled={busy} onClick={()=>onRevise('route')}>重新规划</button>}</div>}
   {!blocking.length&&!!run?.validation?.issues.some(i=>i.status==='unverified')&&<button className="validation-recheck" disabled={busy} onClick={()=>onRevise('route')}>重新检查</button>}
   <details className="assumptions"><summary>费用说明与规划假设</summary>{[...itinerary.assumptions,...itinerary.warnings].map((a,i)=><p key={i}>{a}</p>)}</details>
  </>}
  <footer className="main-footer"><span>用更少的匆忙，换更多的风景。</span><span>TRIPPILOT / V1.2.2</span></footer>
 </main>
}
