import {defineConfig,loadEnv} from 'vite'
import react from '@vitejs/plugin-react'
import {fileURLToPath} from 'node:url'

const root=fileURLToPath(new URL('..',import.meta.url))
const mainPort=loadEnv('development',root,'MAIN_PORT').MAIN_PORT||'8000'
const backendTarget=`http://127.0.0.1:${mainPort}`

export default defineConfig({
 envDir:fileURLToPath(new URL('..',import.meta.url)),
 // The similarly named security code is server-only, including Vite's development env object.
 envPrefix:['VITE_AMAP_JS_KEY'],
 plugins:[react()],
 server:{port:5173,strictPort:true,proxy:{
  '/api':backendTarget,
  '/health':backendTarget,
  '/_AMapService':{
   target:backendTarget,
   configure(proxy){
    // Vite's default proxy error logger would otherwise include SDK query credentials.
    proxy.on('error',(error,request)=>{
     request.url=request.url?.split('?')[0]
     error.message='地图代理连接失败';error.stack='地图代理连接失败'
    })
   },
  },
 }},
})
