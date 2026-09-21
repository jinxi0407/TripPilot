import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'
import {fileURLToPath} from 'node:url'

export default defineConfig({
 envDir:fileURLToPath(new URL('..',import.meta.url)),
 // The similarly named security code is server-only, including Vite's development env object.
 envPrefix:['VITE_AMAP_JS_KEY'],
 plugins:[react()],
 server:{port:5173,strictPort:true,proxy:{
  '/api':'http://127.0.0.1:8000',
  '/health':'http://127.0.0.1:8000',
  '/_AMapService':{
   target:'http://127.0.0.1:8000',
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
