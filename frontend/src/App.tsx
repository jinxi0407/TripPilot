import {useEffect,useState,useRef} from 'react'
import {Compass,ArrowUpRight,AlertCircle,RotateCcw,X} from 'lucide-react'
import {api,active,statusText} from './api/client'
import type {Run,PlanInput,Constraint,Itinerary,ProviderStatus} from './api/types'
import {RequestPanel} from './components/RequestPanel'
import {ItineraryPanel} from './components/ItineraryPanel'
import {ActivityPanel} from './components/ActivityPanel'
export default function App(){
 const [providers,setProviders]=useState<Record<string,ProviderStatus>>({})
 useEffect(()=>{fetch('/health').then(r=>r.json()).then(d=>setProviders(d.provider_status??{})).catch(()=>{})},[])
 const [run,setRun]=useState<Run|null>(null)
 const [previous,setPrevious]=useState<Itinerary|null>(null)
 const [error,setError]=useState('')
 const [submitting,setSubmitting]=useState(false)
 const [selected,setSelected]=useState(1)
 const [retry,setRetry]=useState(0)
 const generation=useRef(0)
 const busy=submitting||active(run)
 const itinerary=run?.itinerary??previous
 useEffect(()=>{
  if(!run||!active(run))return
  let stopped=false;let timer:ReturnType<typeof setTimeout>
  const poll=async()=>{try{const next=await api.get(run.run_id);if(stopped)return;setRun(next);if(active(next))timer=setTimeout(poll,700)}catch(e){if(!stopped)setError(e instanceof Error?e.message:'状态获取失败，请重试。')}}
  timer=setTimeout(poll,150)
  return()=>{stopped=true;clearTimeout(timer)}
 },[run?.run_id,retry,run?.status])
 async function perform(action:()=>Promise<Run>,reset=false){
  setSubmitting(true);setError('');const ticket=++generation.current
  try{const result=await action();if(ticket!==generation.current)return;if(reset){setPrevious(null);setSelected(1)}else if(run?.itinerary)setPrevious(run.itinerary);setRun(result)}catch(e){setError(e instanceof Error?e.message:'请求失败，请重试。')}finally{setSubmitting(false)}
 }
 return <><header className="topbar"><a href="/" className="brand"><span className="brand-icon"><Compass size={23}/></span>TripPilot<span className="brand-beta">BETA</span></a><nav aria-label="主导航"><span className="nav-active">旅行规划</span><a href="#workspace">探索你的下一站 <ArrowUpRight size={14}/></a></nav><div className="provider-indicators" aria-label="数据服务状态">{(['qwen','amap','rail'] as const).map(key=>{const value=(run?.provider_status??providers)[key];const state=value?.state??'PENDING';return <span key={key} className={`provider-state ${state.toLowerCase()}`} title={value?.error_code?`服务错误：${value.error_code}`:value?.model??'以实际调用结果为准'}>{key==='qwen'?'Qwen':key==='amap'?'Amap':'Rail'} {['LIVE','DATASET'].includes(state)?'●':'○'} {state}</span>})}</div></header>
  <div className="breadcrumb"><span>灵感，值得一场出发。</span><span>AI TRAVEL COMPANION <span className="breadcrumb-dot">✦</span> 专为中国旅行而设计</span></div>
  {error&&<div className="error-toast" role="alert"><AlertCircle size={18}/><span>{error} 任务过期时请重新提交。</span><button onClick={()=>{setError('');setRetry(v=>v+1)}}><RotateCcw size={14}/>重试状态</button><button aria-label="关闭错误提示" onClick={()=>setError('')}><X size={15}/></button></div>}
  {run?.simulated_rain&&<div className="simulation-notice">当前版本模拟暴雨用于重规划演示；这不是高德真实天气预报，POI 和路线仍按各自来源展示。</div>}
  {run?.error&&<div className="error-toast" role="alert">{run.error.message}</div>}
  <div className="workspace" id="workspace"><RequestPanel busy={busy} run={run} onSubmit={(input:PlanInput)=>perform(()=>api.create(input),true)} onClarify={(answers:Constraint)=>run&&perform(()=>api.clarify(run.run_id,run.revision,answers))}/><ItineraryPanel run={run} itinerary={itinerary} busy={busy} selected={selected} onSelect={setSelected} onRevise={(reason,budget)=>run&&perform(()=>api.revise(run.run_id,reason,budget===undefined?undefined:{total_budget:budget}))}/><ActivityPanel run={run} itinerary={itinerary} selected={selected}/></div>
  {run&&<div className="run-status" role="status"><span className={active(run)?'pulse':''}/>{statusText[run.status]}{active(run)&&<button onClick={()=>perform(()=>api.cancel(run.run_id))}>取消规划</button>}<small>{run.mode==='fixture'?'模拟结果 · 不代表真实车次、票价或预报':'各项数据来源请查看行程标签'}</small></div>}
 </>
}
