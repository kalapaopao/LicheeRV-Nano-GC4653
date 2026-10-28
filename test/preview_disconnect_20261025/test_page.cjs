// Runs the actual embedded page script without a browser, network or camera.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const input = process.argv[2] ? path.resolve(process.argv[2]) : path.join(__dirname, '../../modules/record80/src/camera_36record.cpp');
const source = fs.readFileSync(input, 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script);
const data = {requested:false, recording:false, written:0, dropped:0, bytes:0, segments:0, error:''};
const flush = async () => { for(let i=0;i<16;i++) await Promise.resolve(); };
function setup(mode='ok') {
    const elements = {};
    for(const id of ['start','stop','status','detail','view','reconnect']) {
        elements[id] = {disabled:true, hidden:true, textContent:'', removed:false, handlers:{},
            remove(){this.removed=true;}, addEventListener(name,fn){this.handlers[name]=fn;}};
    }
    const timers = new Map(), calls = [], handlers = {};
    let timerId=0;
    const state={mode, pending:null};
    const context = vm.createContext({
        document:{getElementById:id=>elements[id]},
        location:{hostname:'127.0.0.1',reload(){}},
        window:{addEventListener:(name,fn)=>{handlers[name]=fn;}},
        AbortController,
        setTimeout:(fn,ms)=>{const id=++timerId;timers.set(id,{fn,ms});return id;},
        clearTimeout:id=>timers.delete(id),
        fetch:(url,options)=>{
            calls.push({url,options});
            if(state.mode==='reject') return Promise.reject(Error('connection refused'));
            if(state.mode==='http') return Promise.resolve({ok:false,status:503});
            if(state.mode==='json') return Promise.resolve({ok:true,json:async()=>{throw Error('bad JSON');}});
            if(state.mode==='hang') return new Promise((resolve,reject)=>{
                state.pending={resolve,reject};
                options.signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true});
            });
            return Promise.resolve({ok:true,json:async()=>({...data})});
        }
    });
    vm.runInContext(script,context);
    return {elements,timers,calls,handlers,state,context,
        async tick(ms){const found=[...timers].find(([,t])=>t.ms===ms);assert.ok(found,`missing ${ms}ms timer`);
            timers.delete(found[0]);found[1].fn();await flush();},
        async run(code){const result=vm.runInContext(code,context);await result;await flush();}};
}
const tests=[];
function test(name,fn){tests.push({name,fn});}
function offline(e){
    assert.equal(e.elements.start.disabled,true);
    assert.equal(e.elements.stop.disabled,true);
    assert.equal(e.elements.reconnect.hidden,false);
    assert.equal(e.elements.view.removed,true);
    assert.match(e.elements.status.textContent,/已停止自动请求/);
    assert.equal(e.timers.size,0);
}
test('healthy polling remains single and updates buttons',async()=>{
    const e=setup();await flush();assert.equal(e.calls.length,1);
    assert.equal(e.elements.start.disabled,false);assert.equal(e.elements.stop.disabled,true);
    assert.equal(e.timers.size,1);await e.tick(1000);assert.equal(e.calls.length,2);assert.equal(e.timers.size,1);
});
test('connection refusal stops all polling',async()=>{
    const e=setup('reject');await flush();offline(e);assert.equal(e.calls.length,1);
    await e.run('refresh(); cmd("start");');assert.equal(e.calls.length,1);
});
test('healthy service then stops: no recurring retries',async()=>{
    const e=setup();await flush();e.state.mode='reject';await e.tick(1000);offline(e);assert.equal(e.calls.length,2);
    await e.run('refresh()');assert.equal(e.calls.length,2);
});
test('HTTP failure stops polling',async()=>{const e=setup('http');await flush();offline(e);});
test('bad JSON stops polling',async()=>{const e=setup('json');await flush();offline(e);});
test('three second timeout aborts pending request',async()=>{
    const e=setup('hang');await flush();assert.equal(e.calls.length,1);
    await e.tick(3000);offline(e);assert.equal(e.calls[0].options.signal.aborted,true);
});
test('slow status requests never overlap',async()=>{
    const e=setup('hang');await flush();await e.run('refresh(); refresh();');assert.equal(e.calls.length,1);
    e.state.pending.resolve({ok:true,json:async()=>({...data})});await flush();assert.equal(e.timers.size,1);
});
test('stream error stops preview and aborts status',async()=>{
    const e=setup('hang');await flush();e.elements.view.handlers.error();await flush();offline(e);
    assert.equal(e.calls[0].options.signal.aborted,true);
});
test('pagehide stops polling',async()=>{
    const e=setup();await flush();e.handlers.pagehide();await flush();offline(e);
});
test('recording action success still refreshes status',async()=>{
    const e=setup();await flush();await e.run('cmd("start")');assert.equal(e.calls.length,3);
    assert.equal(e.calls[1].options.method,'POST');assert.match(e.calls[1].url,/\/start$/);
    assert.equal(e.timers.size,1);
});
test('failed recording POST is not retried',async()=>{
    const e=setup();await flush();e.state.mode='reject';await e.run('cmd("stop")');offline(e);
    assert.equal(e.calls.length,2);await e.run('cmd("stop")');assert.equal(e.calls.length,2);
});
test('reconnect is explicitly user triggered',async()=>{
    assert.match(source,/<button id="reconnect" onclick="location.reload\(\)" hidden>/);
    assert.ok(!script.includes('setInterval('));
});
(async()=>{for(const {name,fn} of tests){await fn();console.log('PASS '+name);}console.log(`PAGE_TESTS_PASS=${tests.length}`);})()
    .catch(error=>{console.error(error);process.exitCode=1;});
