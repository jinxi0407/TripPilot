import {ArrowUpRight,ArrowRight,Sparkles,MapPin,CalendarDays,Wallet,ChevronDown,MessageSquare,RotateCcw} from 'lucide-react'
import {useState} from 'react'
import {DEMO_QUERY} from '../api/client'
import type {PlanInput,Run,Constraint} from '../api/types'
interface Props {demoMode?:boolean;busy:boolean;run:Run|null;onSubmit:(input:PlanInput)=>void;onClarify:(answers:Constraint)=>void}
export function RequestPanel({demoMode=false,busy,run,onSubmit,onClarify}:Props){
 const [query,setQuery]=useState(DEMO_QUERY)
 const [mode,setMode]=useState<'auto'|'fixture'|'live'>('auto')
 const [date,setDate]=useState('')
 const [answerOrigin,setAnswerOrigin]=useState('')
 const [answerDest,setAnswerDest]=useState('')
 const [answerDays,setAnswerDays]=useState(5)
 const missing=run?.missing_fields??(run?.questions??[]).map(q=>({'出发城市':'origin','目的地':'destinations','出行天数':'days','出发日期':'start_date'}[q]??q))
 return <aside className="request-panel">
  <div className="panel-heading"><span className="section-kicker">YOUR NEXT CHAPTER</span><span className="small-icon"><MessageSquare size={16}/></span></div>
  <h2>下一站，想去哪？</h2><p className="muted intro">把想法交给我们，把时间留给旅行。</p>
  <form onSubmit={e=>{e.preventDefault();onSubmit({query,mode,demo:false,constraints:date?{start_date:date}:undefined})}}>
   <label htmlFor="query" className="field-label">告诉 TripPilot 你的旅行想法</label>
   <textarea id="query" value={query} maxLength={4000} onChange={e=>setQuery(e.target.value)} rows={8} required placeholder="出发地、目的地、天数、预算，以及你的旅行偏好…"/>
   <div className="input-count">{query.length} / 4000<span>中文自然语言输入</span></div>
   <label className="field-label" htmlFor="date"><CalendarDays size={14}/> 出发日期</label>
   <input id="date" type="date" value={date} onChange={e=>setDate(e.target.value)}/>
   <details className="execution-settings" open={demoMode}><summary>数据与运行设置</summary><label className="field-label" htmlFor="mode">运行模式</label>
   <div className="select-wrap"><select id="mode" value={mode} onChange={e=>setMode(e.target.value as typeof mode)}><option value="fixture">Mock · 无需 API Key</option><option value="auto">自动 · 按服务配置选择</option><option value="live">Qwen · 需配置模型</option></select><ChevronDown size={15}/></div></details>
   <button className="primary-button" disabled={busy||!query.trim()} type="submit"><Sparkles size={17}/>{busy?'正在为你规划…':'生成我的旅行计划'}<ArrowRight size={17}/></button>
  </form>
  {run?.status==='needs_clarification'&&<form className="clarification" onSubmit={e=>{e.preventDefault();onClarify({...date?{start_date:date}:{},...answerOrigin?{origin:answerOrigin}:{},...answerDest?{destinations:answerDest.split(/[、，,]/).filter(Boolean)}:{},...missing.includes('days')?{days:answerDays}:{}})}}>
   <strong>还差一点信息</strong><p>为了继续规划，请告诉我：</p><ul>{run.questions.map(q=><li key={q}>{q}</li>)}</ul>{missing.includes("start_date")&&<p>请在上方填写出发日期。</p>}
   {missing.includes('origin')&&<input aria-label="补充出发城市" value={answerOrigin} onChange={e=>setAnswerOrigin(e.target.value)} placeholder="出发城市" required/>}
   {missing.includes('destinations')&&<input aria-label="补充目的地" value={answerDest} onChange={e=>setAnswerDest(e.target.value)} placeholder="目的地，用逗号分隔" required/>}
   {missing.includes('days')&&<input aria-label="补充天数" type="number" min="1" max="7" value={answerDays} onChange={e=>setAnswerDays(+e.target.value)}/>}
   <button className="secondary-button" type="submit">补充并继续 <ArrowRight size={14}/></button>
  </form>}
  <div className="divider"/>
  <div className="panel-heading"><span className="field-label">从一段江南旅程开始</span><span className="tiny-pill">精选 Demo</span></div>
  <button className="demo-card" disabled={busy} onClick={()=>{setQuery(DEMO_QUERY);setDate('2026-10-10');onSubmit({query:DEMO_QUERY,mode,demo:true,constraints:{start_date:"2026-10-10"}})}}>
   <div className="demo-art" aria-hidden="true"><span className="art-sun"/><span className="art-hill hill-one"/><span className="art-hill hill-two"/><span className="art-bridge"/><span className="art-boat"/><div className="demo-art-label">江南<br/><small>JIANGNAN JOURNEY</small></div></div>
   <div className="demo-content"><div><strong>三城慢游 · 历史与夜色</strong><span>杭州 · 南京 · 苏州</span></div><ArrowUpRight size={20}/></div>
   <div className="demo-meta"><span><CalendarDays size={13}/>5 天</span><span><Wallet size={13}/>¥4,000</span><span>轻松节奏</span></div>
  </button>
  <p className="fine-print"><MapPin size={13}/> 一键运行所选模式；铁路使用固定日期数据集，其他数据按来源标注。</p>
  <div className="quiet-note"><RotateCcw size={15}/><span>可以随时调整预算、应对天气变化，再规划一次。</span></div>
 </aside>
}
