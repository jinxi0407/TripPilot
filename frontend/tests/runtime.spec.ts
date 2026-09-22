import {test,expect} from '@playwright/test'

test.beforeEach(async({page})=>{
 await page.route('**/api/map/config',r=>r.fulfill({json:{configured:false,missing:['VITE_AMAP_SECURITY_CODE'],service_host:'/_AMapService'}}))
 await page.route('https://**/*',r=>r.abort())
})

test('协议状态来自健康探测，离线后不再显示在线',async({page})=>{
 let online=true
 await page.route('**/health',r=>r.fulfill({json:{provider_status:{},runtime_status:{mcp:{state:online?'CONNECTED':'OFFLINE',tools:online?['search_rail','search_poi','get_weather','calculate_distance','plan_route']:[]},a2a:{transport:online?'ONLINE':'OFFLINE',local:online?'ONLINE':'OFFLINE'},harness:{state:'ACTIVE',policy:{max_react_steps:8,max_tool_calls:40,max_external_calls:160,max_replanning_attempts:2}}}}}))
 await page.goto('/')
 await page.getByRole('button',{name:'演示模式',exact:true}).click()
 const status=page.getByLabel('协议与运行状态')
 await expect(status).toContainText('MCP CONNECTED · 5 tools')
 await expect(status).toContainText('2/2 ONLINE')
 online=false;await page.reload();await page.getByRole('button',{name:'演示模式',exact:true}).click()
 await expect(status).toContainText('MCP OFFLINE')
 await expect(status).toContainText('0/2 ONLINE')
})

test('实际运行的 fallback 状态不会被健康检查覆盖',async({page})=>{
 await page.route('**/api/v1/plans/*',async route=>{
  const response=await route.fetch();const data=await response.json()
  if(data.runtime_status)data.runtime_status.mcp.state='FALLBACK'
  await route.fulfill({json:data})
 })
 await page.goto('/')
 await page.getByRole('button',{name:'演示模式',exact:true}).click()
 await page.getByLabel('运行模式').selectOption('fixture')
 await page.getByRole('button',{name:/三城慢游/}).click()
 await expect(page.getByRole('tab')).toHaveCount(5)
 await expect(page.getByLabel('协议与运行状态')).toContainText('MCP FALLBACK')
})
