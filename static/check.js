
const messages=document.getElementById('messages');
const input=document.getElementById('input');
const sendBtn=document.getElementById('sendBtn');
let ws=null;

// WebSocket
function connect(){
  if(location.protocol==='file:'){
    document.getElementById('messages').innerHTML=
      '<div class="msg bot"><div class="bubble" style="background:color-mix(in oklch,var(--error) 10%,var(--cream-light));color:var(--error)">'+
      '请先运行 <b>start.bat</b> 启动服务<br>然后访问 http://127.0.0.1:8000</div></div>';
    return;
  }
  const p=location.protocol==='https:'?'wss:':'ws:';
  ws=new WebSocket(p+'//'+location.host+'/ws');
  ws.onmessage=e=>{
    const d=JSON.parse(e.data);
    if(d.type==='exercise'){
      removeLoading();
      if(d.reply)addMsg('bot',d.reply);
      renderExercise(d);
      switchPanel('exercise')
    }else{removeLoading();addMsg('bot',d.reply)}
  };
  ws.onerror=()=>{
    document.getElementById('messages').innerHTML=
      '<div class="msg bot"><div class="bubble" style="background:color-mix(in oklch,var(--error) 10%,var(--cream-light));color:var(--error)">'+
      '无法连接服务器<br>请确认已运行 <b>start.bat</b></div></div>';
    setStatus('off','离线');
  };
  ws.onopen=()=>setStatus('on','运行中');
  ws.onclose=()=>{setStatus('off','已断开');setTimeout(connect,2000)};
}
connect();

function setStatus(state,label){
  const dot=document.getElementById('statusDot');
  const txt=document.getElementById('statusText');
  dot.className='dot'+(state==='on'?'':' off');
  dot.style.background=state==='on'?'var(--sage)':'var(--error)';
  txt.textContent=label;
}

function switchPanel(name){
  document.querySelectorAll('.sidebar-nav button').forEach(b=>b.classList.toggle('active',b.dataset.panel===name));
  document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active',p.id==='panel-'+name));
  if(name==='chat')input.focus();
}

function escapeHtml(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}

function linkify(t){
  let h=escapeHtml(t);
  h=h.replace(/\[([^\]]+)\]\(\/files\/(.+)\)/g,(_,t,fp)=>{
    const icon='<svg viewBox="0 0 24 24" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    return '<a href="/files/'+escapeHtml(fp)+'" download style="display:inline-flex;align-items:center;gap:4px;margin:4px 0;padding:6px 14px;background:var(--sage);color:#fff;border-radius:6px;text-decoration:none;font-size:13px;font-weight:600">'+icon+escapeHtml(t)+'</a>';
  });
  h=h.replace(/\/files\/[^\s<"']+/g,m=>{
    let c=m;const pc=(c.match(/\(/g)||[]).length,cc=(c.match(/\)/g)||[]).length;
    if(cc>pc)c=c.replace(/\)+$/,'');
    const fn=c.replace('/files/','').split('/').pop().replace(/^.*[/\\]/,'');
    const icon='<svg viewBox="0 0 24 24" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    return '<a href="'+c+'" download style="display:inline-flex;align-items:center;gap:4px;margin:4px 0;padding:6px 14px;background:var(--sage);color:#fff;border-radius:6px;text-decoration:none;font-size:13px;font-weight:600">'+icon+escapeHtml(fn)+'</a>';
  });
  return h;
}

function addMsg(r,t){
  const d=document.createElement('div');d.className='msg '+r;
  const b=document.createElement('div');b.className='bubble';b.innerHTML=linkify(t);
  d.appendChild(b);messages.appendChild(d);messages.scrollTop=messages.scrollHeight;
  if(typeof renderMathInElement==='function'){
    renderMathInElement(b,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false},{left:'\\(',right:'\\)',display:false}]});
  }
}
function removeLoading(){const l=messages.querySelector('.msg.bot:last-child .bubble.loading');if(l)l.closest('.msg').remove()}
function send(){
  const t=input.value.trim();if(!t)return;
  input.value='';addMsg('user',t);addMsg('bot','…');sendBtn.disabled=true;
  if(ws&&ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify({query:t}));
}
input.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
sendBtn.addEventListener('click',send);

// ═══ Exercise: Card-based with dual-mode (Review / Grading) ═══
let currentQuestions=[];
let exIndex=0;
let exMode='review'; // 'review' | 'grading'
let answered=[];

// Wrap raw LaTeX commands in KaTeX delimiters
function wrapMath(s){
  // 1) Display math: \begin{env}...\end{env} → $$...$$
  s=s.replace(/\\begin\{(\w+)\}([\s\S]*?)\\end\{\1\}/g,(m)=>'$$'+m+'$$');
  // 2) Backslash commands not already inside $...$: wrap in inline $...$
  s=s.replace(/(?<!\$)(\\[a-zA-Z]+(?:\{[^}]*\})?)/g,(m)=>'$'+m+'$');
  // Clean double wrapping
  s=s.replace(/\$\$(\$[^$]+\$)\$\$/g,'$1');
  s=s.replace(/\$\$(\$[^$]+\$)\$\$/g,'$1');
  // Fix cases where empty/trivial inline math was created
  s=s.replace(/\$\\[a-zA-Z]{1,2}\$/g,(m)=>{
    const cmd=m.slice(1,-1);
    if(['\\n','\\t','\\r','\\ ','\\\n'].includes(cmd))return cmd;
    return m;
  });
  return s;
}

function renderExercise(d){
  currentQuestions=(d.questions||[]).map((q,i)=>({id:q.id||i+1,question:q.question,answer:q.answer}));
  answered=[];
  exIndex=0;
  document.getElementById('ex-title').textContent=d.title||'填空题';
  document.getElementById('ex-source').textContent=d.source?'来源: '+d.source:'';
  document.getElementById('ex-empty').style.display='none';
  document.getElementById('ex-questions').style.display='block';
  document.getElementById('ex-results').classList.remove('show');
  document.getElementById('ex-footer').style.display='flex';
  document.getElementById('ex-mode-bar').style.display='flex';
  document.getElementById('ex-answer-btn').style.display='';
  document.getElementById('ex-view-results-btn').classList.remove('show');
  exMode='review';
  document.querySelectorAll('.ex-mode-btn').forEach(b=>{
    b.classList.toggle('active',b.dataset.mode==='review');
  });
  const desc=document.getElementById('ex-mode-desc');
  if(desc)desc.classList.add('hide');
  renderCard();
}

function renderCard(){
  if(!currentQuestions.length)return;
  const q=currentQuestions[exIndex];
  const card=document.getElementById('ex-card');
  const total=currentQuestions.length;
  const processedQuestion=wrapMath(q.question);
  const parts=processedQuestion.split('______');
  let textHtml='';
  parts.forEach((p,i)=>{
    textHtml+=escapeHtml(p);
    if(i<parts.length-1)textHtml+='<span class="blank-highlight">______</span>';
  });
  const answeredInfo=answered.find(a=>a.idx===exIndex);

  if(exMode==='review'){
    card.innerHTML=
      '<div class="ex-card-inner">'+
        '<div class="eq-text"><span class="eq-num">'+(exIndex+1)+'</span>'+textHtml+'</div>'+
        '<div class="ex-answer" id="ex-answer-box">'+
          '<strong>答案：</strong>'+escapeHtml(q.answer)+
        '</div>'+
      '</div>';
    document.getElementById('ex-answer-box').classList.remove('show');
    document.getElementById('ex-answer-btn').className='ex-answer-btn';
    document.getElementById('ex-answer-btn').textContent='显示答案';
    document.getElementById('ex-answer-btn').style.display='';
  } else {
    const isSubmitted=answeredInfo!==undefined;
    const inputClass=isSubmitted?(answeredInfo.correct?'correct':'wrong'):'';
    const submitDisabled=isSubmitted?'disabled':'';
    const submitText=isSubmitted?'已批阅':'提交';
    const inputDisabled=isSubmitted?'disabled':'';
    const inputValue=isSubmitted?escapeHtml(answeredInfo.userAnswer):'';
    let resultHtml='';
    if(isSubmitted){
      if(answeredInfo.correct){
        resultHtml='<div class="ex-result-badge correct">'+
          '<svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'+
          '✓ 正确！</div>';
      } else {
        resultHtml='<div class="ex-result-badge wrong">'+
          '<svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'+
          '✗ 错误，正确答案：<span class="correct-ans"><strong>'+escapeHtml(q.answer)+'</strong></span></div>';
      }
    }
    card.innerHTML=
      '<div class="ex-card-inner">'+
        '<div class="eq-text"><span class="eq-num">'+(exIndex+1)+'</span>'+textHtml+'</div>'+
        '<div class="ex-grading-area">'+
          '<div class="ex-grading-row">'+
            '<input type="text" id="ex-grade-input" class="'+inputClass+'" placeholder="输入你的答案…" '+
              'value="'+inputValue+'" '+inputDisabled+' onkeydown="if(event.key===\"Enter\"&&!this.disabled)submitAnswer()">'+
            '<button class="ex-submit-btn '+submitText+'" id="ex-submit-btn" '+submitDisabled+' onclick="submitAnswer()">'+submitText+'</button>'+
          '</div>'+
          resultHtml+
        '</div>'+
      '</div>';
    document.getElementById('ex-answer-btn').style.display='none';
    if(!isSubmitted){
      setTimeout(()=>{
        const inp=document.getElementById('ex-grade-input');
        if(inp)inp.focus();
      },250);
    }
  }
  document.getElementById('ex-progress').textContent=(exIndex+1)+' / '+total;
  document.getElementById('ex-prev').disabled=(exIndex===0);
  document.getElementById('ex-next').disabled=(exIndex===total-1);
  if(exMode==='grading'){
    const allDone=currentQuestions.every((_,i)=>answered.some(a=>a.idx===i));
    document.getElementById('ex-view-results-btn').classList.toggle('show',allDone);
  }
  if(typeof renderMathInElement==='function'){
    renderMathInElement(card,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false},{left:'\\(',right:'\\)',display:false}]});
  }
}

function nextQuestion(){
  if(document.getElementById('ex-results').classList.contains('show'))return;
  if(exIndex>=currentQuestions.length-1)return;
  const card=document.getElementById('ex-card');
  card.classList.add('slide-left');
  setTimeout(()=>{
    card.classList.remove('slide-left');
    exIndex++;
    renderCard();
  },200);
}

function prevQuestion(){
  if(document.getElementById('ex-results').classList.contains('show'))return;
  if(exIndex<=0)return;
  const card=document.getElementById('ex-card');
  card.classList.add('slide-right');
  setTimeout(()=>{
    card.classList.remove('slide-right');
    exIndex--;
    renderCard();
  },200);
}

function toggleAnswer(){
  const box=document.getElementById('ex-answer-box');
  const btn=document.getElementById('ex-answer-btn');
  if(!box)return;
  const show=!box.classList.contains('show');
  box.classList.toggle('show',show);
  btn.textContent=show?'隐藏答案':'显示答案';
  btn.classList.toggle('revealed',show);
}

function switchExerciseMode(mode){
  if(mode===exMode)return;
  exMode=mode;
  document.querySelectorAll('.ex-mode-btn').forEach(b=>{
    b.classList.toggle('active',b.dataset.mode===mode);
  });
  const desc=document.getElementById('ex-mode-desc');
  if(desc)desc.classList.toggle('hide',mode!=='grading');
  if(mode==='grading'){
    answered=[];
    document.getElementById('ex-view-results-btn').classList.remove('show');
    document.getElementById('ex-results').classList.remove('show');
    document.getElementById('ex-questions').style.display='block';
  }
  if(mode==='review'){
    document.getElementById('ex-results').classList.remove('show');
    document.getElementById('ex-questions').style.display='block';
  }
  renderCard();
}

function submitAnswer(){
  const input=document.getElementById('ex-grade-input');
  const btn=document.getElementById('ex-submit-btn');
  if(!input||input.disabled)return;
  const userAnswer=input.value.trim();
  if(!userAnswer){
    input.focus();
    input.style.borderColor='var(--error)';
    setTimeout(()=>{input.style.borderColor=''},600);
    return;
  }
  const q=currentQuestions[exIndex];
  const correct=normalizeAnswer(userAnswer)===normalizeAnswer(q.answer);
  answered.push({idx:exIndex,userAnswer,correct});
  renderCard();
}

function normalizeAnswer(s){
  return s.replace(/\s+/g,'').toLowerCase()
          .replace(/[，。,．、！？：；（）【】《》""''「」『』]/g,'')
          .replace(/[\u00a0\u3000]/g,'');
}

function showResults(){
  if(!currentQuestions.length)return;
  const total=currentQuestions.length;
  const correctCount=answered.filter(a=>a.correct).length;
  const pct=Math.round((correctCount/total)*100);
  document.getElementById('ex-questions').style.display='none';
  document.getElementById('ex-results').classList.add('show');
  document.getElementById('ex-answer-btn').style.display='none';
  document.getElementById('ex-view-results-btn').classList.remove('show');
  document.getElementById('ex-mode-bar').style.display='none';
  const resultsEl=document.getElementById('ex-results');
  let itemsHtml='';
  currentQuestions.forEach((q,i)=>{
    const a=answered.find(a=>a.idx===i);
    const isCorrect=a?a.correct:false;
    const icon=isCorrect
      ? '<svg class="check" viewBox="0 0 24 24"><path d="M9 11l3 3L22 4" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
      : '<svg class="cross" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    const cls=isCorrect?'correct':'wrong';
    const delay=60*i;
    const processedQ=wrapMath(q.question);
    const parts=processedQ.split('______');
    let qShort=parts.join('____');
    if(qShort.length>60)qShort=qShort.slice(0,58)+'…';
    itemsHtml+=
      '<div class="ex-result-item '+cls+'" style="animation-delay:'+delay+'ms">'+
        '<div class="r-icon">'+icon+'</div>'+
        '<div class="r-body">'+
          '<div class="r-q">'+(i+1)+'. '+escapeHtml(qShort)+'</div>'+
          '<div class="r-ans">'+
            (a?'你的答案：'+escapeHtml(a.userAnswer)+' · ':'')+
            '<strong>正确答案：'+escapeHtml(q.answer)+'</strong>'+
          '</div>'+
        '</div>'+
      '</div>';
  });
  resultsEl.innerHTML=
    '<div class="ex-score-hero">'+
      '<div class="ex-score-ring" style="--pct:'+pct+'%">'+
        '<div class="ex-score-ring-inner">'+
          '<div class="score-num">'+pct+'%</div>'+
          '<div class="score-label">正确率</div>'+
        '</div>'+
      '</div>'+
      '<div class="ex-score-stats">'+
        '<div class="ex-score-stat"><div class="num correct">'+correctCount+'</div><div class="label">正确</div></div>'+
        '<div class="ex-score-stat"><div class="num wrong">'+(total-correctCount)+'</div><div class="label">错误</div></div>'+
        '<div class="ex-score-stat"><div class="num" style="color:var(--text-secondary)">'+total+'</div><div class="label">总计</div></div>'+
      '</div>'+
    '</div>'+
    '<div class="ex-results-list">'+itemsHtml+'</div>'+
    '<div class="ex-results-actions">'+
      '<button class="btn-primary" onclick="switchExerciseMode(\'review\')">📖 复习模式</button>'+
      '<button class="btn-secondary" onclick="switchExerciseMode(\'grading\')">🔄 重做批改</button>'+
    '</div>';
}