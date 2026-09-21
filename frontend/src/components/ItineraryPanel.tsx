import {useState} from 'react'
import {ArrowRight,CalendarDays,TrainFront,MapPin,Clock,ShieldCheck,CloudRain,RefreshCw,AlertCircle,Compass,ChevronDown,Wallet} from 'lucide-react'
import type {Run,Itinerary} from '../api/types'
import {money,clock,categoryText,statusText} from '../api/client'
interface Props{run:Run|null;itinerary:Itinerary|null;busy:boolean;selected:number;onSelect:(day:number)=>void;onRevise:(reason:string,budget?:number)=>void}
export function ItineraryPanel({run,itinerary,busy,selected,onSelect,onRevise}:Props){
 const [newBudget,setNewBudget]=useState(4000)
 const source=(id:string)=>{const e=run?.evidence.find(e=>e.id===id);return e?.source_kind==='live'?'实时来源':e?.source_kind==='dataset'?'数据集':'模拟数据'}
 return <main className="itinerary-panel">
  <div className="section-heading"><div><span className="section-kicker">A LITTLE PLANNING. A LOT OF DISCOVERY.</span><h1>让每一步，都刚刚好<span>。</span></h1><p className="muted">交通、天气与预算，一起安排妥当。</p></div><span className="edition">TRAVEL<br/>BETTER ↗</span></div>
  {!itinerary?<div className="empty-plan">
   <div className="route-illustration" aria-hidden="true"><div className="route-dot start"><TrainFront size={24}/></div><div className="route-line"/><div className="route-dot finish"><Compass size={32}/></div><span className="floating-label">发现，沿途的可能</span></div>
   <span className="section-kicker">YOUR ITINERARY STARTS HERE</span><h2>{busy?'你的旅程，正在成形':run?.status==='failed'?'这次规划暂未完成':'好旅程，从一个想法开始'}</h2><p>{busy?'智能体正在研究目的地、交通和天气。你可以在右侧查看真实执行进度。':run?.status==='failed'?'暂时没有足够的可用证据。请查看错误提示，稍后重试或切换 Mock 模式。':'写下想去的地方，或试试左侧的江南慢游。我们会把零散想法，变成有据可查的旅行计划。'}</p>
   <div className="feature-row"><span><TrainFront size={16}/>城际交通</span><span><MapPin size={16}/>本地探索</span><span><ShieldCheck size={16}/>约束校验</span></div>
  </div>:<>
   <div className="trip-overview"><div className="overview-top"><span className="tiny-pill">YOUR PERSONAL ITINERARY</span><span className="version">版本 {itinerary.version} {busy?'· 正在生成新版':''}</span></div>
    <h2>{[...new Set(itinerary.days.map(d=>d.city))].join(' · ')}<span>慢游计划</span></h2>
    <div className="trip-meta"><span><CalendarDays size={15}/>{itinerary.days.length} 天 · {itinerary.days[0]?.date}</span><span><Wallet size={15}/>{money(itinerary.costs.estimated_total)}</span><span><ShieldCheck size={15}/>{run?statusText[run.status]:'已保留行程'}</span></div>
   </div>
   {run?.validation&&<div className={`validation-banner ${run.validation.valid&&!run.validation.unverified_checks.length?'good':'warning'}`}><ShieldCheck size={18}/><div><strong>{run.validation.valid?(run.validation.unverified_checks.length?'有信息待确认':'已通过当前证据下的约束校验'):'仍有约束冲突，需要调整'}</strong><span>{run.validation.passed_checks}/{run.validation.total_checks} 项检查通过 · {run.mode==='fixture'?'仅验证模拟数据，不代表实时出行保证':'请核对临行信息'}</span></div></div>}
   <div className="day-tabs" role="tablist" aria-label="选择行程日期">{itinerary.days.map(d=><button role="tab" aria-selected={selected===d.day} key={d.day} className={selected===d.day?'selected':''} onClick={()=>onSelect(d.day)}>Day {d.day}<span>{d.city}</span></button>)}</div>
   {itinerary.days.filter(d=>d.day===selected).map(day=><article className="day-card" key={day.day}>
    <div className="day-header"><div className="day-number">{String(day.day).padStart(2,'0')}</div><div><span className="section-kicker">{day.date}</span><h2>{day.origin_city!==day.city?<>{day.origin_city}<ArrowRight size={19}/></>:null}{day.city}<small>{day.day===1?'开启旅程':'继续探索'}</small></h2></div><span className="day-price">{money(day.estimated_cost)}<small>当日预计</small></span></div>
    {day.rail&&<div className="train-ticket"><div className="ticket-label"><TrainFront size={16}/><strong>城际铁路</strong><span>{day.rail.direct?'直达':'中转'} · {source(day.rail.legs[0].evidence_id)}</span></div>{day.rail.legs.map((leg,i)=><div className="train-leg" key={i}><div><strong>{clock(leg.departure_time)}</strong><span>{leg.origin_station.name}</span></div><div className="train-middle"><span>{leg.train_no}</span><div className="rail-line"/><small>{leg.duration} 分钟 · 余票{leg.availability==='unavailable'?'不可用':'未确认'}</small></div><div><strong>{clock(leg.arrival_time)}</strong><span>{leg.destination_station.name}</span></div></div>)}</div>}
    <div className="activity-timeline">{day.activities.map((a,index)=><div className="activity" key={`${a.poi.id}-${index}`}><div className="activity-time">{clock(a.start)}<small>{clock(a.end)}</small></div><div className="timeline-node"/><div className="activity-info"><div className="activity-title"><h3>{a.poi.name}</h3><span className="poi-type">{a.poi.environment==='indoor'?'室内':'户外 / 待确认'}</span></div><p>{a.poi.tags.join(' · ')||'当地探索'} <span>· {source(a.poi.evidence_id)}</span></p><div className="activity-details"><span><Clock size={12}/>{Math.round((Date.parse(a.end)-Date.parse(a.start))/60000)} 分钟</span><span>{a.poi.ticket_price===0?'门票估算免费':`门票 ${money(a.poi.ticket_price)}`}</span></div></div></div>)}</div>
    <details className="route-details" open><summary><MapPin size={15}/> 市内交通 · {day.local_legs.reduce((s,l)=>s+l.route.duration,0)} 分钟<ChevronDown size={15}/></summary><div>{day.local_legs.length?day.local_legs.map((l,i)=><p key={i}><span>{l.route.origin.name} → {l.route.destination.name}</span><strong>{l.route.duration} min</strong></p>):<p>暂无已验证的市内接驳路线。</p>}</div></details>
    <details className="cost-details"><summary>查看当日费用明细 <ChevronDown size={14}/></summary>{day.costs.map(c=><p key={c.id}><span>{categoryText[c.category]} · {c.label}</span><strong>{money(c.amount)}</strong></p>)}</details>
   </article>)}
   <div className="replan-bar"><div><RefreshCw size={18}/><div><strong>计划赶不上变化？</strong><span>重新研究，保留原来的旅程版本。</span></div></div><button disabled={busy} onClick={()=>onRevise('weather')}><CloudRain size={15}/>模拟暴雨 · 重规划</button><button disabled={busy} onClick={()=>onRevise('transport')}><TrainFront size={15}/>更新交通</button></div>
   <div className="budget-update"><label htmlFor="budget">调整总预算</label><span>¥</span><input id="budget" type="number" min="0" value={newBudget} onChange={e=>setNewBudget(Number(e.target.value))}/><button disabled={busy} onClick={()=>onRevise('budget',newBudget*100)}>重新规划</button><button disabled={busy} onClick={()=>onRevise('route')}>重新检查路线</button></div>
   {run?.validation?.issues.length?<details className="issues" open={run.status==='conflict'}><summary><AlertCircle size={15}/>查看 {run.validation.issues.length} 条校验提示</summary>{run.validation.issues.map((i,n)=><p key={n}><strong>{i.day?`Day ${i.day} · `:''}{i.type}</strong>{i.message}<small>{i.suggestion}</small></p>)}</details>:null}
   <details className="assumptions"><summary>费用说明与规划假设</summary>{[...itinerary.assumptions,...itinerary.warnings].map((a,i)=><p key={i}>{a}</p>)}</details>
  </>}
  <footer className="main-footer"><span>用更少的匆忙，换更多的风景。</span><span>TRIPPILOT / V1.1</span></footer>
 </main>
}
