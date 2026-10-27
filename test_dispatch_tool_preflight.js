const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync('publish_once.js','utf8'),ctx);
(async()=>{let commits=0;await assert.rejects(ctx.publishOnce({},null,null,async()=>{commits++;}),/WINDSOR_TOOL_UNAVAILABLE_BEFORE_CAS/);assert.equal(commits,0);console.log('Unavailable action rejected before CAS: PASS; no external actions');})().catch(e=>{console.error(e);process.exitCode=1});
