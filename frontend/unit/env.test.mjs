import {test} from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,writeFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {fileURLToPath} from 'node:url'
import {resolveConfig} from 'vite'

test('开发模式只向客户端暴露 JS Key，安全码与后端 Key 留在服务端',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'trippilot-env-test-'))
 try{
  await writeFile(join(dir,'.env'),'VITE_AMAP_JS_KEY=fake-browser-key\nVITE_AMAP_SECURITY_CODE=fake-private-code\nAMAP_API_KEY=fake-server-key\n')
  const config=await resolveConfig({configFile:fileURLToPath(new URL('../vite.config.ts',import.meta.url)),envDir:dir},'serve')
  assert.equal(config.env.VITE_AMAP_JS_KEY,'fake-browser-key')
  assert.equal(config.env.VITE_AMAP_SECURITY_CODE,undefined)
  assert.equal(config.env.AMAP_API_KEY,undefined)
 }finally{await rm(dir,{recursive:true,force:true})}
})
