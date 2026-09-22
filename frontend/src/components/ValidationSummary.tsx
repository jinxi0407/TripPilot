import type {Issue,Run} from '../api/types'

export const blockingIssues=(issues:Issue[])=>issues.filter(i=>i.blocking&&i.status==='confirmed')
const category=(i:Issue)=>i.type.startsWith('OPENING_')?'opening':i.type.startsWith('WEATHER_')?'weather':i.type.startsWith('BUDGET_')?'budget':i.type==='RAIL_DATASET'||i.type==='FLIGHT_DATASET'?'dataset':i.type.startsWith('HOTEL_')?'hotel':i.type.includes('TRANSPORT')||i.type.includes('ROUTE')?'transport':i.type
export function groupedUncertainty(issues:Issue[]){
 const groups=new Map<string,Issue[]>()
 for(const issue of issues.filter(i=>!i.blocking)){
  const key=category(issue);groups.set(key,[...(groups.get(key)??[]),issue])
 }
 return [...groups].map(([key,items])=>({key,items,label:key==='opening'?`${new Set(items.map(i=>`${i.day}:${i.activity_id??i.target}`)).size} 个景点开放时间待确认`:key==='weather'?'未来天气待临近出发确认':key==='budget'?'部分费用或预算估算待确认':key==='dataset'?'Rail / Flight 为演示数据，请核对实时班次':key==='hotel'?'住宿路线、实时价格与房态待确认':key==='transport'?'部分交通信息待确认':items[0].message}))
}
export function ValidationSummary({run,demoMode}:{run:Run|null;demoMode:boolean}){
 const validation=run?.validation
 if(!validation)return null
 const issues=validation.issues,blocking=blockingIssues(issues),groups=groupedUncertainty(issues)
 return <section aria-label="行程校验" className="validation-summary">
  <div className={`validation-banner ${blocking.length?'warning':'good'}`}><span aria-hidden="true">{blocking.length?'⚠':'✓'}</span><div><strong>{blocking.length?`发现 ${blocking.length} 项需要调整的问题`:'行程已生成'}</strong><span>{blocking.length?'仍有已确认的约束冲突，需要调整':groups.length?'部分外部信息待临行确认':'已通过当前证据下的约束校验'}</span></div></div>
  {blocking.length>0&&<ul className="confirmed-issues">{blocking.map((i,n)=><li key={n}>{i.day?`Day ${i.day} · `:''}{i.message}<small>{i.suggestion}</small></li>)}</ul>}
  {groups.length>0&&<details className="departure-checks"><summary>{groups.length} 项出行前待确认</summary><ul>{groups.map(g=><li key={g.key}>{g.label}</li>)}</ul></details>}
  {demoMode&&<details className="critic-details"><summary>查看 Critic 校验详情</summary><h3>Critic Validation</h3><div className="validation-counts"><span>Confirmed Conflicts {blocking.length}</span><span>Unverified {issues.filter(i=>i.status==='unverified').length}</span><span>Info {issues.filter(i=>i.status==='informational').length}</span></div>{(['confirmed','unverified','informational'] as const).map(status=><section key={status} aria-label={status}>{issues.filter(i=>i.status===status).map((i,n)=><details key={n}><summary>[{i.severity.toUpperCase()}] {i.day?`Day ${i.day} · `:''}{i.type}</summary><p>{i.message}</p><small>{i.suggestion}</small><dl><dt>目标</dt><dd>{i.activity_id??i.target??'全程'}</dd><dt>来源</dt><dd>{i.source}</dd><dt>Blocking</dt><dd>{String(i.blocking)}</dd></dl><pre>{JSON.stringify(i.evidence,null,2)}</pre></details>)}</section>)}</details>}
 </section>
}
export function DayValidation({run,day}:{run:Run|null;day:number}){
 const issues=run?.validation?.issues.filter(i=>i.day===day)??[]
 const blocking=blockingIssues(issues),groups=groupedUncertainty(issues)
 if(!issues.length)return null
 return <div className="day-validation">{blocking.length>0&&<details className="day-conflicts"><summary>⚠ {blocking.length} 项安排冲突</summary>{blocking.map((i,n)=><p key={n}>{i.message}</p>)}</details>}{groups.length>0&&<details><summary>{groups.length} 项待确认</summary><ul>{groups.map(g=><li key={g.key}>{g.label}</li>)}</ul></details>}</div>
}
