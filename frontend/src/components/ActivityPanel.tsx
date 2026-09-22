import {Activity,Check,LoaderCircle,Minus,AlertCircle,Route,Wallet,ArrowUpRight} from 'lucide-react'
import type {Run,Itinerary} from '../api/types'
import {LiveMap} from './LiveMap'
import {money,categoryText} from '../api/client'
export function ActivityPanel({run,itinerary,selected,demoMode=false}:{demoMode?:boolean;run:Run|null;itinerary:Itinerary|null;selected:number}){
 const agents=[['Supervisor','需求理解与任务分配'],['Rail Search','城际铁路研究'],['Amap POI','景点与本地交通'],['Travel Planner','行程编排与调整'],['Critic','可行性与预算校验']]
 const day=itinerary?.days.find(d=>d.day===selected)
 const budget=itinerary?.costs.budget
 const total=itinerary?.costs.estimated_total??0
 return <aside className="activity-panel">
  <section className="agent-card"><div className="panel-heading"><h2><Activity size={17}/>{demoMode?"Agent Activity":"规划进度"}</h2><span className="live-dot"/></div>{demoMode&&<p className="muted">Supervisor → A2A Transport / Local Travel → MCP search_rail / search_poi / search_hotels → Travel Planner · ReAct → Critic → Replanning</p>}
   <div className="agent-list">{agents.map(([name,label],i)=>{const event=run?.trace.filter(t=>t.agent===name).at(-1);const rawStatus=event?.status??'pending';const status=rawStatus==='running'&&run&&['failed','cancelled'].includes(run.status)?'failed':rawStatus;return <div key={name} className={`agent-step ${status}`}><div className="agent-status">{status==='succeeded'?<Check size={15}/>:status==='running'?<LoaderCircle className="spin" size={15}/>:status==='failed'?<AlertCircle size={15}/>:status==='skipped'?<Minus size={15}/>:<span>{String(i+1).padStart(2,'0')}</span>}</div><div><strong>{demoMode?name:label}</strong>{demoMode&&<small>{label}</small>}</div><span className="state-label">{{succeeded:'完成',running:'进行中',failed:'提示',skipped:'跳过',pending:'等待'}[status]}</span></div>})}</div>
   {run&&<details className="trace-detail"><summary>执行记录 · {run.trace.length} 条 <ArrowUpRight size={13}/></summary><ol>{run.trace.map(t=><li key={t.sequence}><span>{String(t.sequence).padStart(2,'0')} · {t.agent}</span>{t.summary}</li>)}</ol></details>}
   {demoMode&&<div className="agent-footnote">{run?`${run.metrics.tool_attempts} 次工具请求 · ${Object.values(run.metrics.agent_steps).reduce((a,b)=>a+b,0)} 个规划步骤`:'可查看工具动作与安全执行摘要'}</div>}
  </section>
  <section className="map-card"><div className="panel-heading"><h2><Route size={17}/>沿途一览</h2><span className="tiny-pill">{day?`DAY ${day.day}`:'路线预览'}</span></div><LiveMap day={day} enabled={run?.mode!=='fixture'}/>
   <div className="map-points">{day?.activities.map((a,i)=><div key={i}><span className="point-number">{i+1}</span><div><strong>{a.poi.name}</strong>{demoMode&&<small>{a.poi.coordinates?`${a.poi.coordinates.longitude.toFixed(4)}, ${a.poi.coordinates.latitude.toFixed(4)} · GCJ-02`:'经纬度待确认'}</small>}</div></div>)??<p className="muted">生成行程后，查看当天的景点与坐标。</p>}</div>
  </section>
  {itinerary&&<section className="budget-card"><div className="panel-heading"><h2><Wallet size={17}/>旅行账本</h2><span className="tiny-pill">估算</span></div><div className="budget-total">{money(total)}<span>/ {money(budget)}</span></div><div className={`budget-track ${budget!=null&&total>budget?'over':''}`}><span style={{width:`${budget?Math.min(100,total/budget*100):0}%`}}/></div>{Object.entries(itinerary.costs.categories).map(([key,value])=><p key={key}><span>{categoryText[key]}</span><strong>{money(value)}</strong></p>)}<div className="budget-note">{itinerary.costs.unknown_items.length?`当前已知预计费用 ${money(itinerary.costs.known_cost??0)}，部分门票/住宿/实时票价待确认。`:budget!=null?(total<=budget?`预算余量 ${money(budget-total)}`:`估算高于预算 ${money(total-budget)}，请核对费用`):'未设置预算上限'}</div></section>}
 </aside>
}
