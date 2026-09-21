import {existsSync} from 'node:fs'
import {defineConfig} from '@playwright/test'
export default defineConfig({workers:2,testDir:'./tests',timeout:30000,use:{baseURL:'http://127.0.0.1:5173',viewport:{width:1440,height:1000},headless:true,launchOptions:{executablePath:existsSync('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')?'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome':undefined,args:['--no-sandbox']}},reporter:'list'})
