import {test,expect,type Page} from '@playwright/test'
const unknown=(type:string,activity_id:string|null=null)=>({type,activity_id,day:1,severity:'warning',status:'unverified',blocking:false,message:'信息待确认',suggestion:'出发前核对',source:'tool',evidence:{},target:activity_id??type})
async function setup(page:Page,conflict?:string){
 await page.route('**/api/map/config',r=>r.fulfill({json:{configured:false,missing:[],service_host:'/_AMapService'}}))
 await page.route('https://**/*',r=>r.abort())
 await page.route('**/api/v1/plans/*',async r=>{
  const res=await r.fetch(),data=await res.json()
  if(data.itinerary){
   const issues:any[]=[unknown('OPENING_HOURS_UNVERIFIED','poi-a'),unknown('OPENING_HOURS_UNVERIFIED','poi-b'),unknown('WEATHER_UNAVAILABLE'),{...unknown('RAIL_DATASET'),day:null,status:'informational',severity:'info'}]
   if(conflict)issues.push({...unknown(conflict,'poi-c'),status:'confirmed',severity:'error',blocking:true,message:'已确认的安排冲突',evidence:{threshold:60,observed:90}})
   data.validation={...data.validation,valid:!conflict,issues,unverified_checks:['hours','weather']}
   data.status=conflict?'conflict':'partial'
  }
  await r.fulfill({json:data})
 })
 await page.goto('/')
 await page.getByText('数据与运行设置',{exact:true}).click()
 await page.getByLabel('运行模式').selectOption('fixture')
 await page.getByRole('button',{name:/三城慢游/}).click()
 await expect(page.getByRole('tab')).toHaveCount(5)
}
test('未知信息显示生成成功、绿色横幅、分类聚合、不显示修复按钮',async({page})=>{
 await setup(page)
 await expect(page.locator('.validation-banner')).toHaveClass(/good/)
 await expect(page.getByText('行程已生成',{exact:true})).toBeVisible()
 await expect(page.getByText('3 项出行前待确认')).toBeVisible()
 await page.getByText('3 项出行前待确认').click()
 await expect(page.locator('.validation-summary')).toContainText('2 个景点开放时间待确认')
 await expect(page.getByLabel('调整总预算')).toHaveCount(0)
 await expect(page.getByRole('button',{name:'重新规划',exact:true})).toHaveCount(0)
 await expect(page.getByRole('button',{name:'重新检查路线',exact:true})).toHaveCount(0)
 await expect(page.getByRole('button',{name:'重新检查',exact:true})).toBeVisible()
 expect(await page.locator('body').innerText()).not.toMatch(/svg|查看\s*\d+\s*条校验提示/)
})
test('Day Card 折叠两个分类，技术模式保留全部目标和证据',async({page})=>{
 await setup(page)
 const day=page.locator('.day-validation')
 // Injected informational rail is global; two uncertainty categories on this day.
 await expect(day.getByText('2 项待确认')).toBeVisible()
 await day.getByText('2 项待确认').click()
 await expect(day).toContainText('2 个景点开放时间待确认')
 await page.getByRole('button',{name:'演示模式',exact:true}).click()
 await page.getByText('查看 Critic 校验详情').click()
 await expect(page.locator('.validation-counts')).toContainText('Confirmed Conflicts 0')
 await expect(page.locator('.validation-counts')).toContainText('Unverified 3')
 await expect(page.locator('.validation-counts')).toContainText('Info 1')
 const details=page.locator('.critic-details section[aria-label="unverified"] details')
 await expect(details).toHaveCount(3)
 await details.first().locator('summary').click()
 await expect(details.first()).toContainText('poi-a')
 await expect(details.first()).toContainText('tool')
})
for(const kind of ['BUDGET_EXCEEDED','TRANSPORT_CONFLICT'])test(`只突出已确认冲突并显示对应操作：${kind}`,async({page})=>{
 await setup(page,kind)
 await expect(page.locator('.validation-banner')).toHaveClass(/warning/)
 await expect(page.getByText('发现 1 项需要调整的问题')).toBeVisible()
 await expect(page.getByRole('button',{name:'重新规划',exact:true})).toBeVisible()
 await expect(page.getByLabel('调整总预算')).toHaveCount(kind==='BUDGET_EXCEEDED'?1:0)
 await expect(page.getByRole('button',{name:'重新检查路线',exact:true})).toHaveCount(kind==='TRANSPORT_CONFLICT'?1:0)
 await expect(page.locator('.confirmed-issues li')).toHaveCount(1)
})
test('未知信息在窄屏不溢出、不出现错误控制台',async({page})=>{
 const errors:string[]=[];page.on('pageerror',()=>errors.push('pageerror'));page.on('console',m=>{if(m.type()==='error')errors.push('console')})
 await page.setViewportSize({width:390,height:844})
 await setup(page)
 await page.getByText('3 项出行前待确认').click()
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
 expect(errors).toEqual([])
})
