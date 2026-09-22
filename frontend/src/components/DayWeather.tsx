import type {Day,Itinerary} from '../api/types'
export function hasForecast(day:Day){const w=day.weather;return Boolean(w&&w.status==='live'&&w.source==='amap_live'&&w.city===day.city&&w.forecast_date===day.date)}
function icon(condition:string){return /雨|雷/.test(condition)?'🌧️':/雪/.test(condition)?'❄️':/阴|云/.test(condition)?'🌤️':/晴/.test(condition)?'☀️':'🌡️'}
function temperature(day:Day){const w=day.weather;if(!w)return '';const lo=w.min_temperature,hi=w.max_temperature;return lo!=null&&hi!=null?`${lo}–${hi}°C`:hi!=null?`${hi}°C`:lo!=null?`${lo}°C`:''}
export function DayWeather({day,demoMode=false}:{day:Day;demoMode?:boolean}){
 const w=day.weather
 return <div className="day-weather" aria-label="当日天气">
  {hasForecast(day)&&w?<><span>{icon(w.weather_condition??'')} {w.weather_condition} <strong>{temperature(day)}</strong></span>{w.precipitation_probability!=null&&<span>降雨概率 {w.precipitation_probability}%</span>}{w.precipitation!=null&&<span>降水量 {w.precipitation} mm</span>}{demoMode&&<small>Amap Weather · LIVE · MCP get_weather</small>}</>:<><span>天气待临近出发确认</span>{w?.status==='simulated'&&<small>模拟天气：{w.weather_condition}，非真实预报</small>}</>}
 </div>
}
export function WeatherOverview({itinerary}:{itinerary:Itinerary}){
 return <div className="weather-overview" aria-label="天气概览">{[...new Set(itinerary.days.map(d=>d.city))].map(city=>{const days=itinerary.days.filter(d=>d.city===city&&hasForecast(d));return <span key={city}>{city} {days.length?days.map(day=><span key={day.day} title={day.date}>{day.date.slice(5)} {icon(day.weather?.weather_condition??'')} {temperature(day)||day.weather?.weather_condition}</span>):'待确认'}</span>})}</div>
}
