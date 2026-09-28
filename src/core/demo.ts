import { detectEvents, type Analysis, type Frame } from './model';
const home = [[9,50],[28,19],[25,41],[25,65],[30,84],[43,28],[40,53],[45,73],[59,17],[56,48],[61,82]];
const away = [[94,50],[77,20],[76,40],[75,62],[78,81],[63,27],[60,48],[63,71],[48,19],[44,53],[49,82]];
export function createDemo(): Analysis {
 const frames: Frame[] = [];
 for(let i=0;i<=240;i++) {
  const time=i/10, progress=Math.min(time/18,1), burst=Math.max(0, Math.min((time-4)/11,1));
  const players = [...home.map(([x,y],j)=>({id:j+1, team:'home' as const, x:x+(j===0?0:burst*(j>7?24:17)), y:y+Math.sin(time*.25+j)*2, confidence:1})), ...away.map(([x,y],j)=>({id:j+12, team:'away' as const, x:x+(j===0?0:progress*10), y:y+Math.sin(time*.2+j)*2, confidence:1}))];
  const carrier = time<4?players[6]:time<9?players[5]:time<15?players[8]:players[9];
  frames.push({time,players,ball:{x:carrier.x+1.5,y:carrier.y+1}});
 }
 return {frames,duration:24,events:detectEvents(frames),source:'simulation',name:'Breaking the press'};
}
