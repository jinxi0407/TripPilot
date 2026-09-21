import type {Run,PlanInput,Constraint} from './types'
async function request<T>(path:string,body?:unknown):Promise<T> {
  const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(15000)})
  const data=await response.json()
  if(!response.ok) throw new Error(data.error?.message??`请求失败（${response.status}）`)
  return data as T
}
export const api={
  create:(input:PlanInput)=>request<Run>('/api/plan',input),
  get:(id:string)=>request<Run>(`/api/v1/plans/${encodeURIComponent(id)}`),
  cancel:(id:string)=>request<Run>(`/api/v1/plans/${encodeURIComponent(id)}/cancel`,{}),
  clarify:(id:string,revision:number,answers:Constraint)=>request<Run>(`/api/v1/plans/${encodeURIComponent(id)}/clarifications`,{expected_revision:revision,answers}),
  revise:(id:string,reason:string,constraints?:Constraint)=>request<Run>(`/api/v1/plans/${encodeURIComponent(id)}/revisions`,{reason,constraints}),
}
export const DEMO_QUERY='我想从上海出发，用5天游玩杭州、南京和苏州。预算4000元，喜欢历史景点和夜景，不想每天太赶。请结合高铁、天气、景点位置和市内交通帮我规划行程。'
export const active=(run:Run|null)=>run?.status==='queued'||run?.status==='running'
export const money=(fen:number|null|undefined)=>fen==null?'待确认':`¥${(fen/100).toLocaleString('zh-CN',{maximumFractionDigits:2})}`
export const clock=(iso:string)=>iso.slice(11,16)
export const statusText:Record<string,string>={queued:'等待规划',running:'正在规划',needs_clarification:'待补充信息',completed:'规划完成',partial:'部分待确认',conflict:'存在约束冲突',failed:'规划未完成',cancelled:'已取消'}
export const categoryText:Record<string,string>={inter_city:'城际交通',local_transport:'市内交通',accommodation:'住宿预算',tickets:'景点门票',food:'餐饮估算',reserve:'备用金'}
