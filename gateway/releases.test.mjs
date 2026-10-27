import { test } from 'node:test';
import assert from 'node:assert/strict';
import { releaseStatus } from './releases.mjs';
test('update checks use this fork and require a published VOS package', async () => {
  const fetcher = async url => {
    assert.equal(url,'https://api.github.com/repos/ictrektech/v-agent/releases/latest');
    return {ok:true,json:async()=>({tag_name:'v0.0.4',assets:[{name:'v-agent_0.0.4_pull.tar'}]})};
  };
  const status = await releaseStatus('0.0.3',{force:true,fetcher});
  assert.equal(status.current_version,'0.0.3');assert.equal(status.latest_version,'0.0.4');assert.equal(status.has_update,true);
  assert.equal((await releaseStatus('0.0.4',{force:true,fetcher})).has_update,false);
  const invalid = await releaseStatus('0.0.3',{force:true,fetcher:async()=>({ok:true,json:async()=>({tag_name:'v1.0.3',assets:[]})})});
  assert.equal(invalid.latest_version,null);assert.ok(invalid.error);
});
