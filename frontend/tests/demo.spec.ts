import {test,expect} from '@playwright/test'

test.beforeEach(async({page})=>{
 await page.route('**/api/map/config',route=>route.fulfill({json:{configured:false,missing:['VITE_AMAP_SECURITY_CODE'],service_host:'/_AMapService'}}))
 await page.route('https://**/*',route=>route.abort())
})

test('一键 Demo、天气修订和预算冲突',async({page})=>{
 const errors:string[]=[]
 page.on('pageerror',e=>errors.push(e.message))
 page.on('console',msg=>{if(msg.type()==='error')errors.push(msg.text())})
 await page.goto('/')
 await page.getByLabel('运行模式').selectOption('fixture')
 await page.getByRole('button',{name:/三城慢游/}).click()
 await expect(page.getByText('已通过当前证据下的约束校验')).toBeVisible()
 await expect(page.getByRole('tab')).toHaveCount(5)
 await expect(page.getByRole('heading',{name:'西湖',exact:true})).toBeVisible()
 await page.screenshot({path:'docs/screenshots/demo-desktop.png',fullPage:true})
 await page.getByRole('button',{name:'模拟暴雨 · 重规划'}).click()
 await expect(page.getByText('版本 2')).toBeVisible()
 await expect(page.getByText('已通过当前证据下的约束校验')).toBeVisible()
 await expect(page.getByRole('heading',{name:'浙江省博物馆',exact:true})).toBeVisible()
 await expect(page.getByRole('heading',{name:'西湖',exact:true})).toHaveCount(0)
 await page.getByLabel('调整总预算').fill('200')
 await page.getByRole('button',{name:'重新规划',exact:true}).click()
 await expect(page.getByText('仍有约束冲突，需要调整')).toBeVisible()
 await expect(page.getByText('预算超限').or(page.getByText('BUDGET_EXCEEDED',{exact:false}))).toBeVisible()
 expect(errors).toEqual([])
})

test('窄屏、日期补充与状态恢复',async({page})=>{
 await page.setViewportSize({width:390,height:844})
 await page.goto('/')
 await page.getByLabel('运行模式').selectOption('fixture')
 await page.getByRole('button',{name:'生成我的旅行计划'}).click()
 await expect(page.getByText('再补充一点，就能出发')).toBeVisible()
 await page.getByLabel('出发日期').fill('2026-10-10')
 await page.getByRole('button',{name:'补充并继续'}).click()
 await expect(page.getByText('已通过当前证据下的约束校验')).toBeVisible()
 await page.getByRole('tab',{name:/Day 3/}).click()
 await expect(page.getByRole('heading',{name:'明城墙',exact:true})).toBeVisible()
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
 await page.screenshot({path:'docs/screenshots/demo-mobile.png',fullPage:true})
})

test('Provider 故障显示受控结果',async({page})=>{
 await page.route('**/api/plan',async route=>{
  const payload=route.request().postDataJSON()
  await route.continue({postData:JSON.stringify({...payload,scenario:'outage'})})
 })
 await page.goto('/')
 await page.getByLabel('运行模式').selectOption('fixture')
 await page.getByRole('button',{name:/三城慢游/}).click()
 await expect(page.getByText('这次规划暂未完成')).toBeVisible()
 await expect(page.getByText('外部服务暂时不可用。',{exact:true})).toBeVisible()
 await page.screenshot({path:'docs/screenshots/provider-outage.png',fullPage:true})
})
