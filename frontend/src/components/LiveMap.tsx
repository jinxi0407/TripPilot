import {useEffect,useRef,useState} from 'react'
import type {Day} from '../api/types'

interface MapInstance {
  on:(event:string,handler:()=>void)=>void
  destroy:()=>void
  clearMap:()=>void
  add:(markers:unknown[])=>void
  setFitView:(markers:unknown[],immediately:boolean,padding:number[],maxZoom:number)=>void
}
interface AmapSDK {
  Map:new(element:HTMLElement,options:Record<string,unknown>)=>MapInstance
  Marker:new(options:Record<string,unknown>)=>unknown
}
declare global {
  interface Window {AMap?:AmapSDK;_AMapSecurityConfig?:{serviceHost:string};tripPilotMapReady?:()=>void}
}
let sdkPromise:Promise<AmapSDK>|null=null
async function loadSDK():Promise<AmapSDK>{
  if(window.AMap)return window.AMap
  if(sdkPromise)return sdkPromise
  sdkPromise=(async()=>{
    const response=await fetch('/api/map/config',{signal:AbortSignal.timeout(8000)})
    if(!response.ok)throw new Error('地图配置服务不可用')
    const config=await response.json() as {configured:boolean;missing:string[];service_host:string}
    if(!config.configured)throw new Error(`地图配置缺失：${config.missing.join('、')}`)
    const key=import.meta.env.VITE_AMAP_JS_KEY
    if(!key)throw new Error('地图 JS Key 未加载，请重启前端')
    // The security code stays on the backend; set serviceHost before loading the SDK.
    window._AMapSecurityConfig={serviceHost:window.location.origin+config.service_host}
    return new Promise<AmapSDK>((resolve,reject)=>{
      const script=document.createElement('script')
      const timer=setTimeout(()=>{script.remove();delete window.tripPilotMapReady;reject(new Error('地图 SDK 加载超时，请检查网络及域名配置'))},15000)
      window.tripPilotMapReady=()=>{clearTimeout(timer);delete window.tripPilotMapReady;if(window.AMap)resolve(window.AMap);else reject(new Error('地图 SDK 初始化失败'))}
      script.onerror=()=>{clearTimeout(timer);script.remove();delete window.tripPilotMapReady;reject(new Error('地图 SDK 加载失败，请检查网络及 JS Key 权限'))}
      script.src=`https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(key)}&callback=tripPilotMapReady`
      script.async=true;document.head.appendChild(script)
    })
  })().catch(error=>{sdkPromise=null;throw error})
  return sdkPromise
}

export function LiveMap({day,enabled=true}:{day:Day|undefined;enabled?:boolean}){
  const container=useRef<HTMLDivElement>(null)
  const instance=useRef<MapInstance|null>(null)
  const [ready,setReady]=useState(false)
  const [error,setError]=useState('')
  useEffect(()=>{
    if(!enabled){setError('Mock 模式：地图未启用，显示 POI 坐标。');return}
    let stopped=false;let timer:ReturnType<typeof setTimeout>|undefined
    loadSDK().then(sdk=>{
      if(stopped||!container.current)return
      const map=new sdk.Map(container.current,{zoom:11,center:[120.15,30.25],viewMode:'2D',resizeEnable:true})
      instance.current=map
      timer=setTimeout(()=>{if(!stopped)setError('地图底图未就绪，请检查 JS Key、安全码、域名白名单及网络。')},20000)
      map.on('complete',()=>{if(!stopped){clearTimeout(timer);setReady(true);setError('')}})
      map.on('error',()=>{if(!stopped){setReady(false);setError('地图鉴权或底图加载失败，请检查 Key、安全码与域名设置。')}})
    }).catch(error=>{if(!stopped)setError(error instanceof Error?error.message:'地图加载失败')})
    return()=>{stopped=true;clearTimeout(timer);instance.current?.destroy();instance.current=null;setReady(false)}
  },[enabled])
  useEffect(()=>{
    if(!ready||!instance.current||!window.AMap)return
    const map=instance.current;map.clearMap()
    const markers=(day?.activities??[]).map((a,i)=>({poi:a.poi,number:i+1})).filter(a=>a.poi.coordinates).map(({poi,number})=>{
      const label=document.createElement('span');label.className='amap-poi-label';label.textContent=`${number}. ${poi.name}`
      // Marker label content is HTML text in the real SDK. textContent above
      // escapes untrusted POI names before serializing that HTML.
      return new window.AMap!.Marker({position:[poi.coordinates!.longitude,poi.coordinates!.latitude],title:poi.name,label:{content:label.outerHTML,direction:'top'}})
    })
    if(markers.length){map.add(markers);map.setFitView(markers,true,[80,35,65,35],15)}
  },[ready,day])
  return <><div ref={container} className="live-map" aria-label="高德实时地图" data-map-state={ready&&!error?'live':error?'failed':'loading'} data-marker-count={ready?day?.activities.filter(a=>a.poi.coordinates).length??0:0}/><div className="map-notice" role="status">{error|| (ready?'● 高德地图 LIVE · 当天景点':'正在加载高德地图…')}</div></>
}
