import type {RuntimeState} from '../api/types'

export function RuntimeStatus({health,execution}:{health:RuntimeState|undefined;execution:RuntimeState|undefined}){
 const runtime=execution??health
 const mcp=runtime?.mcp?.state==='FALLBACK'?runtime.mcp:health?.mcp?.state==='OFFLINE'?health.mcp:runtime?.mcp
 const a2a=runtime?.a2a?{...runtime.a2a}:undefined
 if(a2a&&health?.a2a){for(const key of ['transport','local'] as const){if(health.a2a[key]==='OFFLINE'&&a2a[key]!=='FALLBACK')a2a[key]='OFFLINE'}}
 const online=Object.values(a2a??{}).filter(s=>s==='ONLINE').length
 const fallback=Object.values(a2a??{}).includes('FALLBACK')
 const disabled=!!a2a&&Object.values(a2a).every(s=>s==='DISABLED')
 const policy=runtime?.harness?.policy
 return <div className="runtime-indicators" aria-label="协议与运行状态">
  <span title={mcp?.tools?.join('、')??'等待实际协议探测'}>MCP <strong>{mcp?.state??'PENDING'}</strong>{mcp?.state==='CONNECTED'?` · ${mcp.tools.length} tools`:''}</span>
  <span title={`Transport: ${a2a?.transport??'PENDING'} / Local Travel: ${a2a?.local??'PENDING'}`}>A2A <strong>{fallback?'FALLBACK':disabled?'DISABLED':`${online}/2 ONLINE`}</strong></span>
  <span title={policy?`步骤上限 ${policy.max_react_steps} · 工具预算 ${policy.max_tool_calls} · 外部调用 ${policy.max_external_calls} · 重规划 ${policy.max_replanning_attempts}`:'等待运行配置'}>Harness <strong>{runtime?.harness?.state??'PENDING'}</strong></span>
 <span title="会话上下文与可选本地偏好">Memory <strong>{execution?.memory?.state??health?.memory?.state??'PENDING'}</strong></span></div>
}
