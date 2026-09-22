import {test,expect} from '@playwright/test'

test('地图组件的日切换、名称和视野更新（模拟 SDK）',async({page})=>{
 await page.route('**/api/map/config',route=>route.fulfill({json:{configured:true,missing:[],service_host:'/_AMapService'}}))
 await page.route('https://**/*',async route=>{
  if(new URL(route.request().url()).hostname==='webapi.amap.com'){
   await route.fulfill({contentType:'application/javascript',body:`
    window.AMap={
     Map:class {constructor(el){this.el=el;el.dataset.fitCount='0'} on(event,fn){if(event==='complete')setTimeout(fn,20)} destroy(){this.el.replaceChildren()} clearMap(){this.el.replaceChildren()} add(markers){for(const marker of markers){if(typeof marker.options.label.content!=='string')throw new Error('SDK label must be HTML text');this.el.insertAdjacentHTML('beforeend',marker.options.label.content)}} setFitView(){this.el.dataset.fitCount=String(Number(this.el.dataset.fitCount)+1)}},
     Marker:class {constructor(options){this.options=options}}
    };window.tripPilotMapReady();`})
  }else await route.abort()
 })
 await page.route('**/api/v1/plans/*',async route=>{
  const response=await route.fetch();const data=await response.json()
  // Only the browser-facing response is changed; backend always receives explicit fixture mode.
  await route.fulfill({json:{...data,mode:'qwen'}})
 })
 await page.goto('/')
 await page.getByRole('button',{name:'演示模式',exact:true}).click()
 await page.getByLabel('运行模式').selectOption('fixture')
 await page.getByRole('button',{name:/三城慢游/}).click()
 await expect(page.getByRole('tab')).toHaveCount(5)
 const map=page.getByLabel('高德实时地图')
 await expect(map).toHaveAttribute('data-map-state','live')
 await expect(map).toContainText('西湖')
 await expect(map).toHaveAttribute('data-marker-count',String(await page.locator('.activity-timeline .activity').count()))
 await expect(map).toContainText('1. 西湖')
 const before=Number(await map.getAttribute('data-fit-count'))
 await page.getByRole('tab',{name:/Day 3/}).click()
 await expect(map).toContainText('明城墙')
 await expect(map).not.toContainText('西湖')
 expect(Number(await map.getAttribute('data-fit-count'))).toBeGreaterThan(before)
})

test('缺少安全码显示原因而非 LIVE',async({page})=>{
 await page.route('**/api/map/config',route=>route.fulfill({json:{configured:false,missing:['VITE_AMAP_SECURITY_CODE'],service_host:'/_AMapService'}}))
 await page.goto('/')
 await page.getByRole('button',{name:'演示模式',exact:true}).click()
 await expect(page.getByText('地图配置缺失：VITE_AMAP_SECURITY_CODE')).toBeVisible()
 await expect(page.getByLabel('高德实时地图')).toHaveAttribute('data-map-state','failed')
})

test('Demo 卡片保留用户选择的 LIVE 模式',async({page})=>{
 await page.route('**/api/map/config',route=>route.fulfill({json:{configured:false,missing:['VITE_AMAP_SECURITY_CODE'],service_host:'/_AMapService'}}))
 await page.route('**/api/plan',route=>route.fulfill({status:422,json:{error:{message:'模型未配置（离线测试）'}}}))
 await page.goto('/')
 await page.getByRole('button',{name:'演示模式',exact:true}).click()
 await page.getByLabel('运行模式').selectOption('live')
 const request=page.waitForRequest('**/api/plan')
 await page.getByRole('button',{name:/三城慢游/}).click()
 expect((await request).postDataJSON().mode).toBe('live')
 await expect(page.getByRole('alert')).toContainText('模型未配置')
})
