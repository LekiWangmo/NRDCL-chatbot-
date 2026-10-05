const messages = document.getElementById('messages');
const question = document.getElementById('question');
const send = document.getElementById('send');
const clear = document.getElementById('clear');
const initial = messages.innerHTML;
let busy = false;
function bubble(role, text) {
  const element = document.createElement('div');
  element.className = 'message ' + role;
  const label = document.createElement('div');
  label.className = 'label'; label.textContent = role === 'user' ? 'You' : 'NRDCL assistant';
  const content = document.createElement('div'); content.textContent = text;
  element.append(label, content); messages.append(element);
  messages.scrollTop = messages.scrollHeight;
  return {element, content};
}
async function ask(text) {
  if (busy || text.trim().length < 2) return;
  busy = true; send.disabled = true; clear.disabled = true;
  messages.querySelector('.welcome')?.remove();
  bubble('user', text); question.value = '';
  const reply = bubble('assistant', 'Searching the knowledge base…');
  try {
    const response = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question:text})});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please enter a question of 2–1500 characters.');
    reply.content.textContent = data.answer;
    const sources = document.createElement('div'); sources.className = 'sources';
    for (const source of data.sources) {
      const url = new URL(source.url);
      if (url.protocol !== 'https:' || !['www.nrdcl.bt','nrdcl.bt'].includes(url.hostname)) continue;
      const a = document.createElement('a'); a.href = url.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
      a.textContent = `[${source.id}] ${source.title}`; a.title = `Retrieved ${source.fetched_at}`;
      sources.append(a);
    }
    reply.element.append(sources);
  } catch (error) { reply.content.textContent = error.message; }
  finally {busy = false; send.disabled = false; clear.disabled = false; question.focus(); messages.scrollTop = messages.scrollHeight;}
}
document.getElementById('chat-form').addEventListener('submit', event => {event.preventDefault(); ask(question.value.trim());});
question.addEventListener('keydown', event => {if(event.key === 'Enter' && !event.shiftKey){event.preventDefault(); ask(question.value.trim());}});
messages.addEventListener('click', event => {if(event.target.closest('#suggestions button')) ask(event.target.textContent);});
clear.addEventListener('click', () => {if(!busy){messages.innerHTML = initial; question.value = ''; question.focus();}});
fetch('/api/status').then(response => response.json()).then(data => {
  document.getElementById('status').textContent = data.indexed ? `${data.documents} indexed documents · Updated ${new Date(data.indexed_at).toLocaleDateString()}` : 'Knowledge base not indexed yet — run python ingest.py';
}).catch(() => {document.getElementById('status').textContent = 'Server unavailable';});
