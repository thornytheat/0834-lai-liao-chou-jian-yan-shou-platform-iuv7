import {element} from './client.js';

function block(target,className,content) {
  const node=element('div',content,{class:className});
  target.append(node);
  return node;
}
const note=(target,text)=>block(target,'chart-note',text);

function strip(target,label,value,max,display) {
  const row=block(target,'scale-entry'); block(row,'scale-label',label);
  const ruler=block(row,'scale-rule'); const fill=block(ruler,'fill');
  fill.style.width=`${Math.min(100,100*value/Math.max(1,max))}%`;
  block(row,'scale-readout',display);
}

export function visualize(report,selected) {
  const target=document.querySelector('#visual');
  target.replaceChildren();
  const measurement=report.cases?.find(row=>row.case===selected)?.measure;
  if (!measurement) {block(target,'chart-note','选择有计算值的分组');return;}
  const e=measurement.evidence;

  const wrap=block(target,'risk-rulers');
  strip(wrap,'良批拒收',e.producer_reject_bp,10000,`${(e.producer_reject_bp/100).toFixed(2)}%`);
  strip(wrap,'劣批接收',e.consumer_accept_bp,10000,`${(e.consumer_accept_bp/100).toFixed(2)}%`);
  note(target,`样本缺陷 ${e.observed_defects} · 接收上限 ${e.acceptance_number}`);
}
