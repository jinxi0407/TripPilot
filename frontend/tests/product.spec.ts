import {test,expect} from '@playwright/test'

test.beforeEach(async({page})=>{
 await page.route('**/api/map/config',route=>route.fulfill({json:{configured:false,missing:['VITE_AMAP_SECURITY_CODE'],service_host:'/_AMapService'}}))
 await page.route('https://**/*',route=>route.abort())
})

test('住宿和交通比较来源明确',async({page})=>{
 await page.goto('/')
 await page.getByRole('button',{name:'演示模式',exact:true}).click()
 await page.getByLabel('运行模式').selectOption('fixture')
 await page.getByLabel('告诉 TripPilot 你的旅行想法').fill('2026-10-10 从北京到上海两天，预算4000元，只坐飞机。')
 await page.getByLabel('出发日期').fill('2026-10-10')
 await page.getByRole('button',{name:'生成我的旅行计划'}).click()
 await expect(page.getByLabel('铁路航空比较')).toBeVisible({timeout:15000})
 await expect(page.getByLabel('住宿建议')).toBeVisible()
 await expect(page.getByText('酒店候选来自 POI；实时房价和房态需在 OTA 平台确认，未接入预订。')).toBeVisible()
 await expect(page.getByLabel('铁路航空比较').locator('.source-note')).toContainText('DATASET')
 await page.getByText('查看详细比较',{exact:true}).click()
 await expect(page.getByLabel('铁路航空比较').getByText(/DATASET/).first()).toBeVisible()
 await page.screenshot({path:'docs/screenshots/v12-product-fixture.png',fullPage:true})
})

test('偏好保存和清除控件（隔离持久化）',async({page})=>{
 let prefs:Record<string,unknown>={}
 await page.route('**/api/v1/preferences',async route=>{
  const req=route.request()
  if(req.method()==='POST'){
   const body=req.postDataJSON();expect(body.remember_preferences).toBe(true);prefs=body.preferences
  }
  await route.fulfill({json:{preferences:prefs,saved:true,state:'ACTIVE'}})
 })
 await page.route('**/api/v1/preferences/clear',route=>route.fulfill({json:{preferences:{},cleared:true}}))
 await page.goto('/')
 await page.getByRole('button',{name:'演示模式',exact:true}).click()
 await page.getByText('设置偏好',{exact:true}).click()
 await page.getByLabel('旅行节奏',{exact:true}).selectOption('relaxed')
 await page.getByLabel('避免早班',{exact:true}).check()
 await page.getByLabel('记住我的偏好',{exact:true}).check()
 await page.getByRole('button',{name:'保存偏好',exact:true}).click()
 await expect(page.getByText('偏好已保存到本地')).toBeVisible()
 expect(prefs.travel_pace).toBe('relaxed')
 await page.getByRole('button',{name:'清除偏好',exact:true}).click()
 await expect(page.getByText('长期偏好已清除')).toBeVisible()
})

test('同一会话第二天室内修订保留三天行程',async({page})=>{
 await page.goto('/')
 await page.getByRole('button',{name:'演示模式',exact:true}).click()
 await page.getByLabel('运行模式').selectOption('fixture')
 await page.getByLabel('告诉 TripPilot 你的旅行想法').fill('2026-10-10 杭州三天，预算3000元。')
 await page.getByLabel('出发日期').fill('2026-10-10')
 await page.getByRole('button',{name:'生成我的旅行计划'}).click()
 await expect(page.getByRole('tab')).toHaveCount(3)
 await expect(page.getByRole('button',{name:'生成我的旅行计划'})).toBeEnabled()
 await page.getByLabel('告诉 TripPilot 你的旅行想法').fill('第二天不要安排户外活动。')
 await page.getByRole('button',{name:'生成我的旅行计划'}).click()
 await expect(page.getByRole('tab')).toHaveCount(3)
 await expect(page.getByRole('button',{name:'生成我的旅行计划'})).toBeEnabled()
 await page.getByRole('tab',{name:/Day 2/}).click()
 await expect(page.locator('.activity-timeline .poi-type').first()).toHaveText('室内')
 await expect(page.locator('.activity-timeline').getByText('户外 / 待确认')).toHaveCount(0)
})
