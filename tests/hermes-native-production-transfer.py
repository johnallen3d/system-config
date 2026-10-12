#!/usr/bin/env python3
"""Integrated cold import/reverse fixtures, synthetic secrets/state only."""
import base64
import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import time
import unittest
import subprocess
import sys
import tempfile
import shutil
from types import SimpleNamespace
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result

t=module('transfer',ROOT/'modules/home-manager/hermes-native/production-transfer.py')
r=module('runtime',ROOT/'modules/home-manager/hermes-native/production-runtime.py')
d=module('state_fixture',ROOT/'tests/hermes-native-production-state.py')
p=t.p


class Transfer(unittest.TestCase):
    def setUp(self):
        self.fixture=d.DurableState(); self.fixture.setUp()
        self.root,self.source=self.fixture.root,self.fixture.source
        self.auth={'version':1,'updated_at':'SYNTHETIC ORIGINAL','active_provider':'openai-codex',
            'providers':{'openai-codex':{'auth_mode':'oauth','tokens':{'access_token':'SYNTHETIC-ACCESS','refresh_token':'SYNTHETIC-REFRESH'}}},
            'credential_pool':{'openai-codex':[{'access_token':'SYNTHETIC-ACCESS','refresh_token':'SYNTHETIC-REFRESH'}],
                               'openai-api':[{'api_key':'SYNTHETIC-UNRELATED-DO-NOT-TRANSFER'}]}}
        self.write(self.source,'auth.json',self.auth)
        self.write(self.source,'config.yaml',{'_config_version':44,'model':{'provider':'openai-codex','base_url':'https://chatgpt.com/backend-api/codex'}})
        self.write(self.source,'cron/jobs.json',{'jobs':[{'id':'SYNTHETIC-source-brief','name':'pi-cielo-morning-brief','enabled':True,'schedule':{'kind':'cron','expr':'0 5 * * *','display':'0 5 * * *'}}]})
        self.write(self.source,'SOUL.md',b'SYNTHETIC PRIVATE PERSONALITY\n')
        for n in p.stage.NOTEBOOK_FILES:
            self.write(self.source,'.notebooklm/'+n,{'fixture':'SYNTHETIC PASSIVE CONTEXT'})
        for n in ('state','home','config','cache'):
            (self.root/n).mkdir(mode=0o700)
        self.m={'paths':{n:str(self.root/n) for n in ('state','home','config','cache')},
                'managedAssets':str(ROOT/'modules/home-manager/hermes-native')}
        r.initialize(self.m)
        self.secrets={n:'SYNTHETIC-SECRET-NOT-REAL' for n in ('TELEGRAM_BOT_TOKEN','TELEGRAM_ALLOWED_USERS','TELEGRAM_HOME_CHANNEL','GOG_KEYRING_PASSWORD')}
        self.proof={'running':False,'pid':0,'restartPolicy':'no','managedRetirement':True,'revision':p.stage.REVISION,'observedAt':time.time()}

    def tearDown(self): self.fixture.tearDown()

    def write(self,root,n,value):
        target=root/n; target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        target.write_bytes(value if isinstance(value,bytes) else p.stage.encoded(value)); target.chmod(0o600)

    def cold(self):
        return t.cold_bundle(self.source,source_proof=self.proof,secrets=self.secrets,exclusive_owner=True)

    def test_canonical_empty_keyring_coordination_is_retained_not_transported(self):
        lock=self.source/t.KEYRING_LOCK
        self.write(self.source,t.KEYRING_LOCK,b'')
        self.write(self.source,'gogcli/data/keyring/SYNTHETIC-account',b'SYNTHETIC ENCRYPTED CREDENTIAL')
        before=lock.stat()
        bundle=self.cold()
        after=lock.stat()
        for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_uid','st_gid','st_nlink'):
            self.assertEqual(getattr(before,key),getattr(after,key))
        self.assertEqual(lock.read_bytes(),b'')
        self.assertNotIn(t.KEYRING_LOCK,bundle['files'])
        self.assertEqual(base64.b64decode(bundle['files']['gogcli/data/keyring/SYNTHETIC-account']),b'SYNTHETIC ENCRYPTED CREDENTIAL')
        self.assertEqual(bundle['receipt']['inertCoordinationLocks'][t.KEYRING_LOCK]['inode'],before.st_ino)
        self.assertFalse(bundle['receipt']['inertCoordinationLocks'][t.KEYRING_LOCK]['transported'])
        self.assertEqual(set(p.DATABASES),set(p.DATABASES)&set(bundle['files']))
        with mock.patch.object(p,'checkpoint',wraps=p.checkpoint) as checkpoint:
            lock.write_bytes(b'SYNTHETIC ACTIVE CONTENT')
            with self.assertRaises(ValueError): self.cold()
            checkpoint.assert_not_called()
        lock.write_bytes(b'');lock.chmod(0o644)
        with self.assertRaises(ValueError): self.cold()
        lock.chmod(0o600)
        self.write(self.source,'gogcli/data/keyring/other.lock',b'')
        with self.assertRaises(ValueError): self.cold()

    def test_actual_cold_export_refuses_active_keyring_lock_families_and_inode_drift(self):
        self.write(self.source,t.KEYRING_LOCK,b'')
        lock=self.source/t.KEYRING_LOCK
        for family in ('flock','lockf'):
            code='import fcntl,sys; f=open(sys.argv[1],"r+b"); getattr(fcntl,sys.argv[2])(f.fileno(),fcntl.LOCK_EX); print("HELD",flush=True); sys.stdin.buffer.read(1)'
            child=subprocess.Popen([sys.executable,'-I','-B','-c',code,str(lock),family],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                self.assertEqual(child.stdout.readline(),b'HELD\n')
                with mock.patch.object(p,'checkpoint',wraps=p.checkpoint) as checkpoint:
                    with self.assertRaises((ValueError,BlockingIOError)): self.cold()
                    checkpoint.assert_not_called()
            finally:
                child.communicate(b'x',timeout=10)
            self.assertEqual(child.returncode,0)
        checkpoint=p.checkpoint
        def drift(*args,**kwargs):
            result=checkpoint(*args,**kwargs)
            replacement=lock.with_name('SYNTHETIC-replacement')
            replacement.write_bytes(b'');replacement.chmod(0o600);os.replace(replacement,lock)
            return result
        with mock.patch.object(p,'checkpoint',side_effect=drift):
            with self.assertRaises(ValueError): self.cold()

    def test_pinned_pending_approval_archives_remain_unapproved_outside_active_discovery(self):
        name='pending/memory/deadbeef.json'
        record={'id':'deadbeef','subsystem':'memory','action':'add','summary':'SYNTHETIC proposal, not approved',
                'origin':'background_review','created_at':time.time()-60,
                'payload':{'action':'add','content':'SYNTHETIC unapproved memory'}}
        self.write(self.source,name,record);before=p.signature(self.source/name)
        bundle=self.cold();data=t.decode_bundle(bundle)
        self.assertEqual(json.loads(data[name]),record);self.assertEqual(p.signature(self.source/name),before)
        metadata=bundle['receipt']['pendingApprovalArchives'][name]
        self.assertEqual(metadata['state'],'UNAPPROVED');self.assertEqual(metadata['replay'],'DISABLED')
        self.assertFalse(metadata['activeDiscovery'])
        state,home,checks,mapping=t.transfer_plan(bundle,self.m)
        self.assertFalse(any(n.startswith('pending/') for n in state));self.assertFalse(any(n.startswith('pending/') for n in home))
        self.assertNotIn(name,mapping)
        forged=copy.deepcopy(bundle);forged['receipt']['pendingApprovalArchives'][name]['state']='APPROVED'
        with self.assertRaises(ValueError):t.decode_bundle(forged)
        self.write(self.source,'pending_messages/SYNTHETIC-undelivered.json',{'status':'pending'})
        with self.assertRaises(ValueError):self.cold()
        (self.source/'pending_messages/SYNTHETIC-undelivered.json').unlink()
        self.write(self.source,name,{'status':'delivered','payload':'SYNTHETIC unknown schema'})
        with self.assertRaises(ValueError):self.cold()

    def incident(self,bundle):
        t.import_bundle(bundle,self.m)
        state=Path(self.m['paths']['state']); home=Path(self.m['paths']['home'])
        c=sqlite3.connect(state/'state.db')
        c.execute("INSERT INTO sessions VALUES('SYNTHETIC-native-session')")
        c.execute("INSERT INTO messages VALUES(3,'SYNTHETIC-native-session','SYNTHETIC NATIVE CONVERSATION')")
        c.execute("INSERT INTO delivery_obligations VALUES('SYNTHETIC-native-delivery','delivered','SYNTHETIC NATIVE DELIVERY')")
        c.commit(); c.close()
        latest=copy.deepcopy(self.auth)
        latest['providers']['openai-codex']['tokens'].update(access_token='SYNTHETIC-LATEST-ACCESS',refresh_token='SYNTHETIC-LATEST-REFRESH')
        latest['credential_pool']['openai-codex'][0].update(access_token='SYNTHETIC-LATEST-ACCESS',refresh_token='SYNTHETIC-LATEST-REFRESH')
        latest['updated_at']='SYNTHETIC LATEST'
        self.write(state,'auth.json',json.loads(p.stage.selected_auth(p.stage.encoded(latest))))
        names,_=t.selected_names(state)
        data,receipt=p.checkpoint(state,names,exclusive_owner=True)
        for n in p.stage.NOTEBOOK_FILES:
            name='.notebooklm/'+n; data[name]=(home/name).read_bytes(); receipt['files'][name]=p.signature(home/name)
        normalized,checks=p.normalized_databases(data,receipt)
        proof={'mainPID':0,'activeState':'inactive','ownershipPhase':'STOPPED_REVIEW_REQUIRED','observedAt':time.time()}
        artifact={'schemaVersion':1,'kind':'HERMES763_NATIVE_INCIDENT','namespace':t.NAMESPACE,
            'receipt':receipt,'files':{n:base64.b64encode(b).decode() for n,b in data.items()},'nativeStopped':proof}
        plan=dict(normalized)
        for n in [*t.LIVE_STATE,'auth.json',*['.notebooklm/'+n for n in p.stage.NOTEBOOK_FILES]]:
            if n in data: plan[n]=data[n]
        next_run=datetime.fromtimestamp(time.time()+86400,ZoneInfo('America/New_York')).replace(hour=5,minute=0,second=0,microsecond=0).isoformat()
        plan['cron/jobs.json']=t.reverse_schedule(t.decode_bundle(bundle)['cron/jobs.json'],data['cron/jobs.json'],next_run)
        payload={'schemaVersion':1,'kind':'HERMES763_REVERSE_APPLY','namespace':t.NAMESPACE,
            'sourceBundleSha256':p.stage.digest(p.stage.encoded(bundle)),
            'incidentSha256':p.stage.digest(p.stage.encoded(artifact)),
            'originalSourceFiles':bundle['receipt']['sourceFiles'],'nativeStopped':proof,
            'incidentArtifact':artifact,'checks':checks,'files':{n:base64.b64encode(b).decode() for n,b in plan.items()}}
        approval={'kind':'JOHN_INCIDENT_RESTORE','action':'RESTORE_NAS_RUNTIME_STATE_NOT_VAULT',
            'confirmedBy':'John Allen','namespace':t.NAMESPACE,'incidentSha256':payload['incidentSha256'],
            'sourceBundleSha256':payload['sourceBundleSha256'],'reversePayloadSha256':p.stage.digest(p.stage.encoded(payload)),
            'approvedAt':time.time()-1,'expiresAt':time.time()+120}
        # This is a synthetic approval-shaped fixture, not real user authority.
        return payload,approval

    @unittest.skipUnless(sys.platform=='linux' and os.environ.get('HERMES763_TASK_SOURCES'),'pinned supported Codex client fixture')
    def test_supported_public_probe_client_one_request_no_tools_history_or_retry(self):
        from agent import auxiliary_client
        from hermes_cli import auth_codex
        import io
        state=Path(self.m['paths']['state'])
        self.write(state,'config.yaml',{'model':{'provider':'openai-codex','default':'gpt-5.4'}})
        result=SimpleNamespace(output=[{'type':'message','content':[{'type':'output_text','text':'HERMES_NATIVE_OK'}]}])
        client=SimpleNamespace(api_key='SYNTHETIC',base_url='https://chatgpt.com/backend-api/codex',
            responses=SimpleNamespace(create=mock.Mock(return_value=result)),close=mock.Mock())
        output=SimpleNamespace(buffer=io.BytesIO()); exists=Path.exists
        def no_workstation(path): return False if str(path)=='/home/johna/.codex' else exists(path)
        credentials={'provider':'openai-codex','source':'hermes-auth-store','base_url':str(client.base_url),'api_key':'SYNTHETIC'}
        with mock.patch.object(r,'acceptance_context'),mock.patch.object(r,'install_provider_hook'), \
             mock.patch.object(Path,'exists',autospec=True,side_effect=no_workstation), \
             mock.patch.object(auth_codex,'resolve_codex_runtime_credentials',return_value=credentials) as resolver, \
             mock.patch.object(auxiliary_client,'_create_openai_client',return_value=client) as factory, \
             mock.patch.object(r.sys,'stdout',output),mock.patch.dict(os.environ,{'HOME':self.m['paths']['home'],'HERMES_HOME':str(state)},clear=True):
            r.public_probe_child(self.m)
        resolver.assert_called_once_with(); factory.assert_called_once_with(api_key='SYNTHETIC',base_url=str(client.base_url),max_retries=0,timeout=25)
        client.responses.create.assert_called_once(); client.close.assert_called_once()
        kwargs=client.responses.create.call_args.kwargs
        self.assertNotIn('tools',kwargs); self.assertFalse(kwargs.get('store'))
        self.assertNotIn('previous_response_id',kwargs)
        # Supported SDK bypass may encode the body; inspect only this synthetic request.
        body=kwargs.get('extra_body',kwargs)
        self.assertIn(r.PUBLIC_PROBE_PROMPT,json.dumps(body,default=str))
        self.assertEqual(output.buffer.getvalue(),b'HERMES_NATIVE_OK\n')

    def test_closed_initialize_preserves_existing_receipt_and_lock_inode(self):
        state=Path(self.m['paths']['state']); lock=state/'writer.lock'
        before=(lock.stat().st_dev,lock.stat().st_ino)
        owner=(state/'controller/ownership.json').read_bytes()
        r.initialize(self.m)
        self.assertEqual(before,(lock.stat().st_dev,lock.stat().st_ino))
        self.assertEqual(owner,(state/'controller/ownership.json').read_bytes())
        self.assertFalse((state/'auth.json').exists())

    def test_provider_preflight_accepts_only_canonical_secret_not_pass_flags_or_profile_paths(self):
        state=Path(self.m['paths']['state']);before=p.signature(state/'controller/ownership.json')
        with mock.patch.object(r,'check'),mock.patch.object(r.subprocess,'run') as execute:
            for request in [{'calendar':'PASS','weather':'PASS'},{'GOG_HOME':'/home/johna/.config/gogcli'},
                            {'GOG_KEYRING_PASSWORD':''},{'GOG_KEYRING_PASSWORD':'SYNTHETIC\nINJECT'}]:
                with self.assertRaisesRegex(ValueError,'canonical Calendar secret'):r.engineering_providers(self.m,request)
            execute.assert_not_called()
        self.assertFalse((state/'controller/engineering-providers.json').exists())
        self.assertEqual(p.signature(state/'controller/ownership.json'),before)

    def test_integrated_readiness_refuses_caller_flags_and_never_creates_authority(self):
        state=Path(self.m['paths']['state']); before=p.signature(state/'controller/ownership.json')
        with mock.patch.object(r,'check') as check,mock.patch.object(r.subprocess,'run') as execute:
            for request in [{'productionReady':True},{'runtimeGuard':'PASS','coldImport':'PASS'},{}]:
                with self.assertRaisesRegex(ValueError,'fixed actual integration'): r.engineering_ready(self.m,request)
            check.assert_not_called();execute.assert_not_called()
        self.assertFalse((state/'controller/task-code.json').exists());self.assertFalse((state/'controller/engineering.json').exists())
        self.assertEqual(p.signature(state/'controller/ownership.json'),before)

    def test_managed_canonical_skills_describe_only_available_guarded_routes(self):
        assets=Path(self.m['managedAssets'])
        label=(assets/'skills/personal/food-label/SKILL.md').read_text()
        recipe=(assets/'skills/personal/recipe/SKILL.md').read_text()
        self.assertIn('mise run save-common-food -- FOOD_JSON',label)
        self.assertIn('vlt vault=Personal read file=health/common-foods.yaml',label)
        self.assertIn('does not expose `ocr-label`',label)
        self.assertNotIn('mise run ocr-label',label)
        self.assertNotIn('vlt vault="Personal" files',label)
        self.assertIn('mise run save-recipe -- recipes/NAME.md MARKDOWN_JSON PLAN_JSON',recipe)
        self.assertIn('mise run save-common-food -- FOOD_JSON',recipe)
        config=p.stage.load_config(t.production_config({'config.yaml':(self.source/'config.yaml').read_bytes()},Path(self.m['paths']['state'])))
        self.assertFalse(config['kanban']['dispatch_in_gateway']);self.assertFalse(config['kanban']['notify_in_gateway'])
        self.assertEqual(config['platform_toolsets']['telegram'],['terminal','skills','vision','memory'])
        self.assertEqual(r.terminal_request({'command':'vlt vault=Personal read file=health/common-foods.yaml'}),
            {'operation':'read','task':'vlt','args':['vault=Personal','read','file=health/common-foods.yaml']})
        for command in ['mise run ocr-label -- /tmp/SYNTHETIC.png','vlt vault=Personal files',
                        'vlt vault=Personal write file=health/common-foods.yaml']:
            try:
                request=r.terminal_request({'command':command})
                with self.assertRaises(ValueError):r.read_task(dict(self.m,vault=str(self.source)),request['task'],request['args'])
            except ValueError:pass

    def test_engineering_runner_rejects_pass_flags_and_profile_or_live_vault_inputs(self):
        state=Path(self.m['paths']['state']); before=(state/'controller/ownership.json').read_bytes()
        with mock.patch.object(r.subprocess,'run') as execute:
            for request in [{'productionReady':True,'runtimeGuard':'PASS'},
                            {'taskSources':'/home/johna/notes'}, {'taskSources':'/home/johna/.codex'},
                            {'taskSources':'/tmp/arbitrary/reviewed-code'}]:
                with self.assertRaisesRegex(ValueError,'fixture input|retained reviewed'): r.engineering_components(self.m,request)
            execute.assert_not_called()
        self.assertEqual((state/'controller/ownership.json').read_bytes(),before)
        self.assertFalse((state/'controller/engineering.json').exists())
        identity=r.engineering_identity(self.m)
        self.assertIn('plugins/macros/__init__.py',identity)
        self.assertIn('skills/health/food/scripts/adjust-food-log',identity)
        self.m['fixtureClosure']='SYNTHETIC changed metadata'
        self.assertNotEqual(identity,r.engineering_identity(self.m))

    def test_revocation_precedes_stop_and_keeps_failure_sticky(self):
        state=Path(self.m['paths']['state']); owner_path=state/'controller/ownership.json'
        before=owner_path.read_bytes()
        with mock.patch.object(r.subprocess,'run') as execute:
            with self.assertRaisesRegex(ValueError,'NAS/CLOSED'): r.stop(self.m)
            execute.assert_not_called()
        self.assertEqual(owner_path.read_bytes(),before)
        owner=json.loads(before); owner.update(owner='native',phase='NATIVE_LIVE')
        self.write(state,'controller/ownership.json',owner)
        def failed_stop(argv,**kwargs):
            revoked=t.load(owner_path)
            self.assertEqual(revoked['phase'],'STOPPED_REVIEW_REQUIRED')
            self.assertTrue(all(revoked[k]=='DISABLED' for k in ['poller','scheduler','vaultWrites','providerRefresh']))
            raise subprocess.CalledProcessError(1,['SYNTHETIC STOP'])
        with mock.patch.object(r.subprocess,'run',side_effect=failed_stop):
            with self.assertRaises(subprocess.CalledProcessError): r.stop(self.m)
        self.assertEqual(t.load(owner_path)['phase'],'STOPPED_REVIEW_REQUIRED')
        self.assertFalse((state/'auth.json').exists())

    def test_incident_export_requires_revoked_ownership_even_when_unit_stopped(self):
        with mock.patch.object(t.subprocess,'run') as execute:
            with self.assertRaisesRegex(ValueError,'ownership must be revoked'): t.native_stopped(self.m)
            execute.assert_not_called()
        state=Path(self.m['paths']['state']); owner=t.load(state/'controller/ownership.json')
        owner.update(owner='native',phase='STOPPED_REVIEW_REQUIRED')
        self.write(state,'controller/ownership.json',owner)
        result=subprocess.CompletedProcess([],0,stdout=b'ActiveState=inactive\nMainPID=0\n')
        with mock.patch.object(t.subprocess,'run',return_value=result):
            self.assertEqual(t.native_stopped(self.m)['ownershipPhase'],'STOPPED_REVIEW_REQUIRED')

    def arming_fixture(self):
        self.proof.update(imageID='sha256' + ':' + '1'*64,containerID='2'*64,retirementSha256='3'*64)
        bundle=self.cold(); t.import_bundle(bundle,self.m)
        self.m.update(runtimeEngineeringReady=True,service='hermes-production.service')
        state=Path(self.m['paths']['state'])
        self.write(state,'controller/engineering-components.json',{'fixture':'SYNTHETIC COMPONENT EVIDENCE NOT REAL READINESS'})
        engineering={'kind':'HERMES763_ACTUAL_PRESTOP_ENGINEERING','namespace':t.NAMESPACE,
                     'productionReady':True,'code':r.engineering_identity(self.m),
                     'componentEvidenceSha256':p.signature(state/'controller/engineering-components.json')['sha256']}
        engineering.update({k:'PASS' for k in ['runtimeGuard','coldImport','reverseRecovery','writerGate',
                                             'nasRedeployGuard','sourceProfileCAS','syncthingConvergence']})
        self.write(state,'controller/engineering.json',engineering)
        now=time.time()
        peers={name:{'folderID':'notes','type':'sendreceive','paused':False,'state':'idle',
                'connectedPeers':{'omarchy':['mac'],'mac':['nas','omarchy'],'nas':['mac']}[name],
                'completion':100,'needItems':0,'needBytes':0,'errors':0,'pullErrors':0,'conflicts':[],
                'observedAt':now} for name in ['omarchy','mac','nas']}
        request={'kind':'HERMES763_ARM_STOPPED_SOURCE','namespace':t.NAMESPACE,
                 'sourceBundleSha256':t.load(state/'controller/import.json')['sourceBundleSha256'],
                 'sourceProof':copy.deepcopy(self.proof),'peers':peers,
                 'freeze':{'manualConfirmationSource':'JOHN_EXECUTION_WINDOW','coordinator':'omarchy',
                           'excludedWriters':sorted(r.writer_module().WRITERS),'confirmedAt':now-1,'expiresAt':now+120}}
        return request

    def armed_acceptance_fixture(self):
        state=self.root/'hermes-native/production/baseline-0.21.2'
        state.mkdir(mode=0o700,parents=True); self.m['paths']['state']=str(state)
        vault=self.root/'acceptance-vault'; vault.mkdir(mode=0o700); (vault/'journal').mkdir(mode=0o700)
        self.m['vault']=str(vault); r.initialize(self.m)
        request=self.arming_fixture()
        self.m['environment']={'HERMES_HOME':str(state),'HOME':self.m['paths']['home']}
        # Metadata environment is part of the immutable engineering identity.
        engineering=t.load(state/'controller/engineering.json'); engineering['code']=r.engineering_identity(self.m)
        self.write(state,'controller/engineering.json',engineering)
        with mock.patch.object(r,'systemctl',return_value=b'ActiveState=inactive\nMainPID=0\nRestart=no\nRefuseManualStart=yes\n'):
            r.arm(self.m,request,ingress=lambda:{'ok':True,'result':[]})
        self.secrets.update(TELEGRAM_ALLOWED_USERS='123',TELEGRAM_HOME_CHANNEL='123')
        self.write(state,'.secrets.json',self.secrets)
        return state,vault,request

    def test_closed_public_probe_and_caller_acceptance_flags_are_inert(self):
        execute=mock.Mock()
        with self.assertRaisesRegex(ValueError,'ownership'): r.public_probe(self.m,run=execute)
        execute.assert_not_called()
        state,vault,request=self.armed_acceptance_fixture()
        forged={'namespace':t.NAMESPACE,'kind':'HERMES763_ACTUAL_INITIAL_ACCEPTANCE',
                'sourceBundleSha256':request['sourceBundleSha256']}
        forged.update({k:'PASS' for k in ['tinyPublicProbe','actualInboundZeroModelCommand','syncedCanary',
                                         'realZeroModelBrief','soleNativeRuntime']})
        unchanged=p.signature(state/'controller/ownership.json')
        with self.assertRaisesRegex(ValueError,'no PASS flags'): r.initial_live(self.m,forged)
        self.assertEqual(p.signature(state/'controller/ownership.json'),unchanged)

    def test_public_probe_is_claimed_once_before_gateway_without_bot_secrets(self):
        state,vault,request=self.armed_acceptance_fixture()
        execute=mock.Mock(return_value=subprocess.CompletedProcess([],0,stdout=b'HERMES_NATIVE_OK\n',stderr=b''))
        command=['SYNTHETIC-SEALED-NAMESPACE','gateway-child']
        with mock.patch.object(r,'systemctl',return_value=b'ActiveState=inactive\nMainPID=0\n'), \
             mock.patch.object(r,'gateway_command',return_value=command.copy()):
            self.assertEqual(r.public_probe(self.m,run=execute)['tinyPublicProbe'],'DONE')
            with self.assertRaisesRegex(ValueError,'already claimed'): r.public_probe(self.m,run=execute)
        self.assertEqual(execute.call_count,1)
        argv=execute.call_args.args[0]; self.assertEqual(argv[-1],'public-probe-child')
        self.assertNotIn('TELEGRAM_BOT_TOKEN',execute.call_args.kwargs['env'])
        receipt=t.load(state/'controller/acceptance-probe.json')
        self.assertEqual(receipt['tools'],[]); self.assertFalse(receipt['privateContext'])
        self.assertEqual(t.load(state/'controller/ownership.json')['phase'],'NATIVE_ARMED')

    def test_public_probe_uncertainty_revokes_and_never_retries(self):
        state,vault,request=self.armed_acceptance_fixture()
        execute=mock.Mock(side_effect=subprocess.TimeoutExpired('SYNTHETIC',40))
        with mock.patch.object(r,'systemctl',return_value=b'ActiveState=inactive\nMainPID=0\n'), \
             mock.patch.object(r,'gateway_command',return_value=['SYNTHETIC','gateway-child']):
            with self.assertRaises(subprocess.TimeoutExpired): r.public_probe(self.m,run=execute)
            with self.assertRaisesRegex(ValueError,'ownership'): r.public_probe(self.m,run=execute)
        self.assertEqual(execute.call_count,1)
        self.assertEqual(t.load(state/'controller/acceptance-probe.json')['status'],'CLAIMED')
        self.assertEqual(t.load(state/'controller/ownership.json')['phase'],'STOPPED_REVIEW_REQUIRED')

    def test_actual_inbound_ack_is_bound_to_existing_private_chat_and_not_retried(self):
        state,vault,request=self.armed_acceptance_fixture()
        send=mock.Mock(return_value={'ok':True,'result':{'message_id':456,'chat':{'id':123}}})
        with self.assertRaisesRegex(ValueError,'private owner chat'): r.acceptance_status(self.m,['999','999','1','2'],send=send)
        send.assert_not_called()
        args=['123','123','1','2']
        r.acceptance_status(self.m,args,send=send); r.acceptance_status(self.m,args,send=send)
        self.assertEqual(send.call_count,1)
        with self.assertRaisesRegex(ValueError,'already claimed'): r.acceptance_status(self.m,['123','123','3','4'],send=send)
        self.assertEqual(t.load(state/'controller/acceptance-inbound.json')['status'],'DONE')
        self.assertEqual(t.load(state/'controller/acceptance-inbound.json')['provider'],'NO_MODEL')

    def test_inbound_uncertain_delivery_retains_claim_without_retry(self):
        state,vault,request=self.armed_acceptance_fixture()
        send=mock.Mock(side_effect=TimeoutError('SYNTHETIC DELIVERY UNCERTAINTY'))
        with self.assertRaises(TimeoutError): r.acceptance_status(self.m,['123','123','1','2'],send=send)
        with self.assertRaisesRegex(ValueError,'already claimed'): r.acceptance_status(self.m,['123','123','1','2'],send=send)
        self.assertEqual(send.call_count,1)
        self.assertEqual(t.load(state/'controller/acceptance-inbound.json')['status'],'CLAIMED')

    @unittest.skipUnless(sys.platform=='linux' and os.environ.get('HERMES763_TASK_SOURCES'),'pinned Telegram ingress fixture')
    def test_actual_pinned_ingress_gate_has_no_model_or_other_command_before_live(self):
        from gateway.run_inbound import GatewayInboundMixin
        from gateway.platforms.event import MessageEvent,MessageType
        from gateway.session import SessionSource
        from gateway.config import Platform
        state,vault,request=self.armed_acceptance_fixture()
        upstream=mock.AsyncMock(return_value='SYNTHETIC ORIGINAL LIVE HANDLER')
        broker=mock.Mock(return_value='ACKNOWLEDGED')
        runner=SimpleNamespace(_is_user_authorized_for_source=mock.Mock(return_value=True))
        source=SessionSource(platform=Platform.TELEGRAM,chat_id='123',user_id='123')
        def event(text='/status'):
            return MessageEvent(text=text,message_type=MessageType.COMMAND,source=source,
                                message_id='1',platform_update_id=2)
        with mock.patch.object(GatewayInboundMixin,'_handle_message',upstream):
            r.install_acceptance_ingress(self.m,broker)
            asyncio.run(GatewayInboundMixin._handle_message(runner,event()))
            self.assertEqual(broker.call_args.args[0]['operation'],'acceptance-status')
            self.assertEqual(broker.call_args.args[0]['args'],['123','123','1','2'])
            upstream.assert_not_awaited()
            broker.reset_mock(); runner._is_user_authorized_for_source.return_value=False
            asyncio.run(GatewayInboundMixin._handle_message(runner,event()))
            broker.assert_not_called(); upstream.assert_not_awaited()
            runner._is_user_authorized_for_source.return_value=True
            for text in ['/restart','hello private model prompt','/status extra']:
                broker.reset_mock(); asyncio.run(GatewayInboundMixin._handle_message(runner,event(text)))
                self.assertEqual(broker.call_args.args[0]['operation'],'acceptance-unexpected')
                self.assertNotIn(text,json.dumps(broker.call_args.args[0]))
            upstream.assert_not_awaited()
            owner=t.load(state/'controller/ownership.json'); owner['phase']='NATIVE_LIVE'
            self.write(state,'controller/ownership.json',owner)
            self.assertEqual(asyncio.run(GatewayInboundMixin._handle_message(runner,event())),
                             'SYNTHETIC ORIGINAL LIVE HANDLER')
            upstream.assert_awaited_once()

    def test_brief_claim_precedes_actual_write_and_uncertain_delivery_has_no_retry(self):
        state,vault,request=self.armed_acceptance_fixture()
        for name,kind in [('acceptance-inbound.json','HERMES763_ACTUAL_INBOUND_ZERO_MODEL_COMMAND'),
                          ('acceptance-canary.json','HERMES763_ACTUAL_SYNCED_CANARY')]:
            self.write(state,'controller/'+name,{'namespace':t.NAMESPACE,'kind':kind,'status':'DONE',
                'sourceBundleSha256':request['sourceBundleSha256'],'code':r.engineering_identity(self.m),
                'fixture':'SYNTHETIC NOT REAL PRODUCTION ACCEPTANCE'})
        scope=dict(request['freeze'],schemaVersion=1,namespace=t.NAMESPACE,
                   files=list(r.task_targets('morning-brief',[])),nonce='SYNTHETIC-BRIEF-'+'a'*24)
        output=b'SYNTHETIC PRIVATE ZERO MODEL BRIEF\n'
        def task(*args):
            self.assertEqual(t.load(state/'controller/acceptance-brief.json')['status'],'CLAIMED')
            return {'task':'COMPLETE','provider':'NO_MODEL','outputBase64':base64.b64encode(output).decode()}
        execute=mock.Mock(side_effect=task); send=mock.Mock(side_effect=TimeoutError('SYNTHETIC UNCERTAINTY'))
        with mock.patch.object(r,'maintenance_task',execute):
            with self.assertRaises(TimeoutError): r.acceptance_brief(self.m,{'scope':scope},None,send=send)
            with self.assertRaisesRegex(ValueError,'already claimed'):
                r.acceptance_brief(self.m,{'scope':scope},None,send=send)
        self.assertEqual(execute.call_count,1); self.assertEqual(send.call_count,1)
        self.assertEqual((state/'controller/acceptance-brief.stdout').read_bytes(),output)
        self.assertEqual(t.load(state/'controller/acceptance-brief.json')['status'],'CLAIMED')

    def test_noeffect_continuation_requires_fresh_source_window_preserves_checks_and_never_reimports(self):
        state,vault,request=self.armed_acceptance_fixture()
        owner=t.load(state/'controller/ownership.json')
        owner.update(phase='STOPPED_REVIEW_REQUIRED',poller='DISABLED',scheduler='DISABLED',
                     vaultWrites='DISABLED',providerRefresh='DISABLED')
        self.write(state,'controller/ownership.json',owner)
        current=r.engineering_identity(self.m); previous=dict(current,**{'production-runtime.py':'0'*64})
        arming=t.load(state/'controller/arming.json'); arming['code']=previous
        self.write(state,'controller/arming.json',arming)
        preserved={}
        for name,kind in [('acceptance-probe.json','HERMES763_ACTUAL_TINY_PUBLIC_PROBE'),
                          ('acceptance-inbound.json','HERMES763_ACTUAL_INBOUND_ZERO_MODEL_COMMAND'),
                          ('acceptance-canary.json','HERMES763_ACTUAL_SYNCED_CANARY')]:
            self.write(state,'controller/'+name,{'namespace':t.NAMESPACE,'kind':kind,'status':'DONE',
                'sourceBundleSha256':owner['sourceBundleSha256'],'code':previous})
            preserved[name]=p.signature(state/'controller'/name)['sha256']
        self.write(state,'controller/acceptance-brief.json',{'status':'CLAIMED','fixture':'SYNTHETIC NO EFFECT'})
        self.write(state,'writer-reservation.json',{'status':'STOPPED_REVIEW_REQUIRED','fixture':'SYNTHETIC NO EFFECT'})
        proof={'kind':'HERMES763_PROFILE_SYMLINK_NO_EFFECT_CONTINUATION','namespace':t.NAMESPACE,
               'previousCode':previous,'initialGeneration':'SYNTHETIC INITIAL GENERATION',
               'sourceBundleSha256':owner['sourceBundleSha256'],'preservedReceipts':preserved,
               'claimSha256':p.signature(state/'controller/acceptance-brief.json')['sha256'],
               'reservationSha256':p.signature(state/'writer-reservation.json')['sha256']}
        fresh={'freeze':request['freeze'],'sourceProof':request['sourceProof'],'peers':request['peers']}
        baseline={n:p.signature(state/n) for n in ['auth.json','state.db','shared-state.db','cron/jobs.json']}
        with mock.patch.object(r,'engineering_evidence',return_value={}), \
             mock.patch.object(r,'brief_noeffect',return_value=proof),mock.patch.object(t,'import_bundle') as imported, \
             mock.patch.object(r,'telegram_send_once') as sent:
            expired=copy.deepcopy(fresh); expired['freeze']['expiresAt']=time.time()-1
            with self.assertRaisesRegex(ValueError,'freeze'): r.continue_brief(self.m,expired)
            changed=copy.deepcopy(fresh); changed['sourceProof']['retirementSha256']='9'*64
            with self.assertRaisesRegex(ValueError,'stopped NAS'): r.continue_brief(self.m,changed)
            result=r.continue_brief(self.m,fresh)
            self.assertEqual(result['continuation'],'PROVEN_NO_EFFECT')
            imported.assert_not_called(); sent.assert_not_called()
        self.assertEqual({n:p.signature(state/n) for n in baseline},baseline)
        self.assertEqual(t.load(state/'controller/ownership.json')['phase'],'NATIVE_ARMED')
        for name,sha in preserved.items():
            self.assertEqual(p.signature(state/'controller'/name)['sha256'],sha)
            kind=t.load(state/'controller'/name)['kind']
            self.assertEqual(r.recorded_acceptance(self.m,name,kind)[1],sha)
        self.assertEqual(t.load(state/'controller/acceptance-brief.json')['status'],'CLAIMED')
        self.assertEqual(t.load(state/'writer-reservation.json')['status'],'STOPPED_REVIEW_REQUIRED')
        # A changed historic successful receipt is not silently re-certified.
        self.write(state,'controller/acceptance-inbound.json',{'status':'DONE'})
        with self.assertRaisesRegex(ValueError,'retained acceptance'):
            r.recorded_acceptance(self.m,'acceptance-inbound.json','HERMES763_ACTUAL_INBOUND_ZERO_MODEL_COMMAND')

    def test_final_only_continuation_preserves_all_done_receipts_and_rejects_partial_or_drift(self):
        state,vault,request=self.armed_acceptance_fixture()
        owner=t.load(state/'controller/ownership.json');owner.update(phase='STOPPED_REVIEW_REQUIRED',
            poller='DISABLED',scheduler='DISABLED',vaultWrites='DISABLED',providerRefresh='DISABLED')
        self.write(state,'controller/ownership.json',owner)
        current=r.engineering_identity(self.m);previous=dict(current,**{'production-runtime.py':'0'*64})
        historical=dict(previous,**{'production-writers.py':'1'*64})
        arming=t.load(state/'controller/arming.json');arming['code']=previous
        self.write(state,'controller/arming.json',arming)
        archive=state/'controller/synthetic-noeffect-archive';archive.mkdir(mode=0o700)
        preserved={};review={'kind':'HERMES763_PROFILE_SYMLINK_NO_EFFECT_CONTINUATION','namespace':t.NAMESPACE,
            'code':previous,'previousCode':historical,'sourceBundleSha256':owner['sourceBundleSha256'],
            'archive':str(archive),'preservedReceipts':preserved}
        target=r.task_targets('morning-brief',[])[0];self.write(vault,target,b'SYNTHETIC ALREADY ACCEPTED JOURNAL\n')
        output=b'SYNTHETIC ALREADY DELIVERED BRIEF\n';self.write(state,'controller/acceptance-brief.stdout',output)
        post=r.writer_module().manifest(vault,[target])
        for name,kind in r.ACCEPTANCE_KINDS:
            v={'namespace':t.NAMESPACE,'kind':kind,'status':'DONE','sourceBundleSha256':owner['sourceBundleSha256'],
               'code':previous if name=='acceptance-brief.json' else historical}
            if name=='acceptance-brief.json':v.update(files=[target],postimages=post,provider='NO_MODEL',
                convergence='ACTUAL_ALL_PEER_METADATA',deliveryMessageID='SYNTHETIC ACK',outputSha256=p.stage.digest(output))
            self.write(state,'controller/'+name,v)
            if name!='acceptance-brief.json':
                self.write(archive,name,v);preserved[name]=p.signature(state/'controller'/name)['sha256']
        self.write(state,'controller/acceptance-noeffect-continuation.json',review)
        self.write(state,'writer-reservation.json',{'status':'COMPLETE','postimages':post})
        self.write(state,'controller/final-gate-evidence.json',{'fixture':'SYNTHETIC FOCUSED EVIDENCE'})
        arming['freeze']['expiresAt']=time.time()-1;self.write(state,'controller/arming.json',arming)
        fresh={k:request[k] for k in ['sourceProof','peers']}
        names=['auth.json','state.db','shared-state.db','cron/jobs.json','writer-reservation.json',
               'controller/acceptance-brief.stdout',*('controller/'+name for name,_ in r.ACCEPTANCE_KINDS)]
        baseline={n:p.signature(state/n) for n in names};journal=p.signature(vault/target)
        with mock.patch.object(r,'check'),mock.patch.object(r.t,'native_stopped'), \
             mock.patch.object(r,'previous_final_gate',return_value='SYNTHETIC AUDITED OLD GENERATION'), \
             mock.patch.object(r,'final_gate_evidence',return_value={}), \
             mock.patch.object(r,'next_distinct_brief',return_value='SYNTHETIC PINNED FIXTURE SEPARATELY'), \
             mock.patch.object(t,'import_bundle') as imported,mock.patch.object(r,'telegram_send_once') as sent, \
             mock.patch.object(r,'maintenance_task') as task:
            invented=copy.deepcopy(fresh);invented['freeze']=request['freeze']
            with self.assertRaisesRegex(ValueError,'no vault mutation'):r.continue_live(self.m,invented)
            stale=copy.deepcopy(fresh);stale['sourceProof']['observedAt']=time.time()-31
            with self.assertRaisesRegex(ValueError,'stopped NAS'):r.continue_live(self.m,stale)
            changed=copy.deepcopy(fresh);changed['sourceProof']['imageID']='sha256:'+'9'*64
            with self.assertRaisesRegex(ValueError,'stopped NAS'):r.continue_live(self.m,changed)
            self.write(state,'controller/initial-acceptance.json',{'fixture':'SYNTHETIC PARTIAL'})
            with self.assertRaisesRegex(ValueError,'partial initial'):r.final_gate_ready(self.m)
            (state/'controller/initial-acceptance.json').unlink()
            old=(vault/target).read_bytes();(vault/target).write_bytes(b'SYNTHETIC CONCURRENT WRITER\n')
            with self.assertRaisesRegex(ValueError,'postimage'):r.final_gate_ready(self.m)
            self.write(vault,target,old)
            # Refresh the fixture's own signature after its deliberate drift, not production.
            post=r.writer_module().manifest(vault,[target]);v=t.load(state/'controller/acceptance-brief.json');v['postimages']=post
            self.write(state,'controller/acceptance-brief.json',v);self.write(state,'writer-reservation.json',{'status':'COMPLETE','postimages':post})
            baseline={n:p.signature(state/n) for n in names};journal=p.signature(vault/target)
            proof=r.final_gate_ready(self.m);result=r.continue_live(self.m,fresh)
            self.assertEqual(result['continuation'],'FINAL_ACTIVATION_ONLY')
            self.assertEqual(proof['acceptance'],'ALL_FOUR_DONE_NOT_REPEATED')
            r.revoke(self.m)
            resumed=r.continue_live(self.m,fresh)
            self.assertEqual(resumed['continuation'],'FINAL_ACTIVATION_ONLY')
            final=r.t.load(state/'controller/acceptance-final-gate-continuation.json')
            self.assertTrue((Path(final['archive'])/'failed-final-gate.json').exists())
            r.revoke(self.m)
            with self.assertRaisesRegex(ValueError,'contained failed supervisor'):r.continue_live(self.m,fresh)
            # No third generic retry; fixture re-arms only for receipt validation below.
            owned=r.t.load(state/'controller/ownership.json');owned.update(phase='NATIVE_ARMED',poller='ENABLED')
            self.write(state,'controller/ownership.json',owned)
            imported.assert_not_called();sent.assert_not_called();task.assert_not_called()
        self.assertEqual({n:p.signature(state/n) for n in names},baseline)
        self.assertEqual(p.signature(vault/target),journal)
        self.assertEqual(t.load(state/'controller/ownership.json')['scheduler'],'DISABLED')
        for name,kind in r.ACCEPTANCE_KINDS:self.assertEqual(r.recorded_acceptance(self.m,name,kind)[1],baseline['controller/'+name]['sha256'])
        self.write(state,'controller/acceptance-brief.json',{'status':'DONE'})
        with self.assertRaisesRegex(ValueError,'retained acceptance'):
            r.recorded_acceptance(self.m,'acceptance-brief.json','HERMES763_ACTUAL_ZERO_MODEL_BRIEF')

    def canary_scopes(self,request):
        base=dict(request['freeze'],schemaVersion=1,namespace=t.NAMESPACE,files=[r.CANARY_NAME])
        return {'createScope':dict(base,nonce='SYNTHETIC-CREATE-'+'a'*24),
                'removeScope':dict(base,nonce='SYNTHETIC-REMOVE-'+'b'*24)}

    def test_canary_exact_create_remove_retained_preimage_and_no_existing_overwrite(self):
        state,vault,request=self.armed_acceptance_fixture()
        callbacks=lambda m,scope,observe:(observe,lambda names:None)
        with mock.patch.object(r,'maintenance_callbacks',side_effect=callbacks):
            result=r.acceptance_canary(self.m,self.canary_scopes(request),lambda names:copy.deepcopy(request['peers']))
        self.assertEqual(result['syncedCanary'],'DONE'); self.assertFalse((vault/r.CANARY_NAME).exists())
        receipt=t.load(state/'controller/acceptance-canary.json'); self.assertEqual(receipt['status'],'DONE')
        retained=list((state/'reservation-evidence').glob('*.preimages/journal/hermes-native-763-canary.md'))
        self.assertEqual(len(retained),1); self.assertEqual(retained[0].read_bytes(),r.CANARY_BYTES)
        with self.assertRaisesRegex(ValueError,'already claimed'):
            r.acceptance_canary(self.m,self.canary_scopes(request),lambda names:copy.deepcopy(request['peers']))

    def test_canary_conflict_or_existing_path_is_preserved_and_never_deleted(self):
        state,vault,request=self.armed_acceptance_fixture(); path=vault/r.CANARY_NAME
        self.write(vault,r.CANARY_NAME,b'SYNTHETIC USER CONTENT MUST SURVIVE\n'); before=p.signature(path)
        with mock.patch.object(r,'maintenance_callbacks',return_value=(lambda names:copy.deepcopy(request['peers']),lambda names:None)):
            with self.assertRaisesRegex(ValueError,'existing canary path'):
                r.acceptance_canary(self.m,self.canary_scopes(request),lambda names:copy.deepcopy(request['peers']))
        self.assertEqual(p.signature(path),before)
        self.assertEqual(t.load(state/'writer-reservation.json')['status'],'STOPPED_REVIEW_REQUIRED')

    def test_maintenance_waits_only_after_own_scan_and_never_waives_conflicts(self):
        state,vault,request=self.armed_acceptance_fixture()
        scope=self.canary_scopes(request)['createScope']; clean=copy.deepcopy(request['peers'])
        busy=copy.deepcopy(clean); busy['mac'].update(state='syncing',completion=90,needItems=1)
        scan=mock.Mock()
        with mock.patch.object(r,'local_writer_callbacks',return_value=(None,scan)),mock.patch.object(r.time,'sleep'):
            observer,selected_scan=r.maintenance_callbacks(self.m,scope,mock.Mock(return_value=busy))
            with self.assertRaisesRegex(ValueError,'convergence required'): observer([r.CANARY_NAME])
            rows=mock.Mock(side_effect=[busy,clean])
            observer,selected_scan=r.maintenance_callbacks(self.m,scope,rows)
            selected_scan([r.CANARY_NAME]); self.assertEqual(observer([r.CANARY_NAME]),clean)
            self.assertEqual(rows.call_count,2)
            conflict=copy.deepcopy(busy); conflict['mac']['conflicts']=['SYNTHETIC-CONFLICT']
            rows=mock.Mock(return_value=conflict)
            observer,selected_scan=r.maintenance_callbacks(self.m,scope,rows); selected_scan([r.CANARY_NAME])
            with self.assertRaisesRegex(ValueError,'conflict/error/topology'): observer([r.CANARY_NAME])
            self.assertEqual(rows.call_count,1)

    def test_closed_gateway_start_cannot_resolve_credentials_or_start_unit(self):
        with mock.patch.object(r.subprocess,'Popen') as spawn,mock.patch.object(r,'systemctl') as systemd:
            for operation in [r.gateway,r.start]:
                with self.assertRaisesRegex(ValueError,'ownership'): operation(self.m)
            spawn.assert_not_called(); systemd.assert_not_called()
        self.assertFalse((Path(self.m['paths']['state'])/'auth.json').exists())

    def test_arming_requires_actual_current_window_source_peers_empty_ingress_and_import(self):
        request=self.arming_fixture(); state=Path(self.m['paths']['state']); owner_before=(state/'controller/ownership.json').read_bytes()
        source_before={n:p.signature(self.source/n) for n in t.selected_names(self.source)[0]}
        ingress=mock.Mock(return_value={'ok':True,'result':[]})
        bad=copy.deepcopy(request); bad['freeze']['expiresAt']=time.time()-1
        with self.assertRaisesRegex(ValueError,'freeze'): r.arm(self.m,bad,ingress=ingress)
        ingress.assert_not_called()
        bad=copy.deepcopy(request); bad['peers'].pop('nas')
        with self.assertRaisesRegex(ValueError,'peers'): r.arm(self.m,bad,ingress=ingress)
        ingress.assert_not_called()
        inactive=b'ActiveState=inactive\nMainPID=0\nRestart=no\nRefuseManualStart=yes\n'
        with mock.patch.object(r,'systemctl',return_value=inactive):
            result=r.arm(self.m,request,ingress=ingress)
        self.assertEqual(result['ownership'],'NATIVE_ARMED')
        owner=t.load(state/'controller/ownership.json')
        self.assertEqual(owner['scheduler'],'DISABLED'); self.assertEqual(owner['providerRefresh'],'ENABLED')
        self.assertEqual(owner['phase'],'NATIVE_ARMED')
        self.assertEqual(source_before,{n:p.signature(self.source/n) for n in source_before})
        self.assertEqual(t.load(state/'controller/pending-ingress.json')['result'],[])
        with self.assertRaisesRegex(ValueError,'rearming'): r.arm(self.m,request,ingress=ingress)

    def test_pending_ingress_is_retained_without_ack_drop_or_implicit_retry(self):
        request=self.arming_fixture(); state=Path(self.m['paths']['state']); before=(state/'controller/ownership.json').read_bytes()
        inactive=b'ActiveState=inactive\nMainPID=0\nRestart=no\nRefuseManualStart=yes\n'
        pending={'ok':True,'result':[{'fixture':'SYNTHETIC PENDING'}]}
        with mock.patch.object(r,'systemctl',return_value=inactive):
            with self.assertRaisesRegex(ValueError,'pending Telegram'): r.arm(self.m,request,ingress=lambda:pending)
            self.assertEqual((state/'controller/ownership.json').read_bytes(),before)
            self.assertEqual(t.load(state/'controller/pending-ingress.json'),pending)
            retry=mock.Mock(return_value={'ok':True,'result':[]})
            with self.assertRaisesRegex(ValueError,'previous ingress'): r.arm(self.m,request,ingress=retry)
            retry.assert_not_called()

    @unittest.skipUnless(sys.platform=='linux' and os.environ.get('HERMES763_TASK_SOURCES'),'pinned Hermes schedule fixture')
    def test_initial_live_is_not_final_acceptance_and_uses_pinned_ny_schedule(self):
        vault=self.root/'acceptance-vault'; vault.mkdir(mode=0o700); self.m['vault']=str(vault)
        self.m['operator']=os.environ.get('HERMES_PRODUCTION_OPERATOR',str(Path(self.m['managedAssets'])/'production-runtime.py'))
        request=self.arming_fixture(); state=Path(self.m['paths']['state'])
        with mock.patch.object(r,'systemctl',return_value=b'ActiveState=inactive\nMainPID=0\nRestart=no\nRefuseManualStart=yes\n'):
            r.arm(self.m,request,ingress=lambda:{'ok':True,'result':[]})
        acceptance={'sourceProof':copy.deepcopy(request['sourceProof']),
                    'peers':copy.deepcopy(request['peers']),'freeze':copy.deepcopy(request['freeze'])}
        for name,kind in [('acceptance-probe.json','HERMES763_ACTUAL_TINY_PUBLIC_PROBE'),
                          ('acceptance-inbound.json','HERMES763_ACTUAL_INBOUND_ZERO_MODEL_COMMAND'),
                          ('acceptance-canary.json','HERMES763_ACTUAL_SYNCED_CANARY'),
                          ('acceptance-brief.json','HERMES763_ACTUAL_ZERO_MODEL_BRIEF')]:
            self.write(state,'controller/'+name,{'namespace':t.NAMESPACE,'kind':kind,'status':'DONE',
                'sourceBundleSha256':request['sourceBundleSha256'],'code':r.engineering_identity(self.m),
                'files':[],'postimages':{},'fixture':'SYNTHETIC NOT ACTUAL PRODUCTION ACCEPTANCE'})
        self.m['managedAssets']=str(ROOT/'modules/home-manager/hermes-native')
        with mock.patch.dict(os.environ,{'HOME':self.m['paths']['home'],'HERMES_HOME':str(state),
                                         'HERMES_TIMEZONE':'America/New_York','TZ':'America/New_York'},clear=True):
            unchanged={n:p.signature(state/n) for n in ['controller/ownership.json','cron/jobs.json']}
            with r.writer_module().held_lock(state/'cron/.jobs.lock'):
                with self.assertRaises((ValueError,BlockingIOError)): r.initial_live(self.m,acceptance)
            self.assertEqual(unchanged,{n:p.signature(state/n) for n in unchanged})
            # The actual foreground gateway must retain its single-runtime lock.
            original_read=Path.read_bytes
            def read_process(path):
                if str(path)=='/proc/12345/cmdline':
                    return (self.m['operator']+'\x00gateway\x00').encode()
                return original_read(path)
            def service(*args):
                return (b'ActiveState=active\nMainPID=12345\nRestart=no\n' if args[1]==self.m['service']
                        else b'ActiveState=inactive\nMainPID=0\n')
            with r.writer_module().held_lock(state/'controller/runtime.lock'), \
                 mock.patch.object(r,'systemctl',side_effect=service), \
                 mock.patch.object(Path,'read_bytes',autospec=True,side_effect=read_process):
                result=r.initial_live(self.m,acceptance)
        self.assertEqual(result['status'],'native live/observation pending'); self.assertFalse(result['finalAcceptance'])
        when=datetime.fromisoformat(result['nextBrief']).astimezone(ZoneInfo('America/New_York'))
        self.assertEqual((when.hour,when.minute),(5,0))
        jobs=t.load(state/'cron/jobs.json')['jobs']; self.assertEqual(len(jobs),1)
        self.assertTrue(jobs[0]['no_agent']); self.assertTrue(jobs[0]['enabled']); self.assertEqual(jobs[0]['deliver'],'telegram')
        self.assertEqual(jobs[0]['schedule'],{'kind':'cron','expr':'0 5 * * *','display':'0 5 * * *'})
        self.assertEqual(jobs[0]['id'],'SYNTHETIC-source-brief')
        self.assertEqual(t.load(state/'controller/ownership.json')['observationStatus'],'PENDING')

    @unittest.skipUnless(sys.platform=='linux' and os.environ.get('HERMES763_TASK_SOURCES'),'pinned supported NY scheduler fixture')
    def test_acceptance_day_is_not_redelivered_before_five_and_dst_next_daily_is_exact(self):
        with mock.patch.dict(os.environ,{'HERMES_TIMEZONE':'America/New_York','TZ':'America/New_York'}):
            for literal in ['2026-10-11T03:00:00-04:00','2026-10-11T06:00:00-04:00',
                            '2026-03-07T03:00:00-05:00','2026-10-31T03:00:00-04:00']:
                now=datetime.fromisoformat(literal).astimezone(ZoneInfo('America/New_York'))
                when=datetime.fromisoformat(r.next_distinct_brief({'kind':'cron','expr':'0 5 * * *'},now)).astimezone(ZoneInfo('America/New_York'))
                self.assertEqual((when.hour,when.minute),(5,0)); self.assertEqual((when.date()-now.date()).days,1)
                self.assertGreater(when.timestamp(),now.timestamp())

    @unittest.skipUnless(sys.platform=='linux' and os.environ.get('HERMES763_TASK_SOURCES'),'pinned preserved schedule fixture')
    def test_preserved_canonical_schedule_display_passes_without_rewriting_or_weakening_daily_guard(self):
        schedule={'kind':'cron','expr':'0 5 * * *','display':'0 5 * * *'};before=copy.deepcopy(schedule)
        with mock.patch.dict(os.environ,{'HERMES_TIMEZONE':'America/New_York','TZ':'America/New_York'}):
            now=datetime.fromisoformat('2026-10-11T08:36:40-04:00')
            self.assertEqual(r.next_distinct_brief(schedule,now),'2026-10-12T05:00:00-04:00')
            self.assertEqual(schedule,before)
            for wrong in [dict(schedule,expr='0 6 * * *'),dict(schedule,display='0 6 * * *'),
                          dict(schedule,timezone='UTC'),dict(schedule,kind='interval')]:
                with self.assertRaisesRegex(ValueError,'original NY daily'):r.next_distinct_brief(wrong,now)

    def test_reverse_scheduler_retains_job_identity_source_routes_and_latest_outcome_without_replay(self):
        source={'jobs':[{'id':'same-id','name':'pi-cielo-morning-brief','schedule':{'kind':'cron','expr':'0 5 * * *'},
                         'enabled':True,'no_agent':True,'script':'NAS-ORIGINAL.sh','workdir':'/NAS/notes','deliver':'telegram',
                         'last_run_at':'SYNTHETIC OLD','repeat':{'times':None,'completed':4}}]}
        native=copy.deepcopy(source)
        native['jobs'][0].update(script='NATIVE.sh',workdir='/NATIVE/notes',last_run_at='SYNTHETIC LATEST',
                               last_status='delivery_failed',last_delivery_error='SYNTHETIC uncertain',fire_claim={'by':'SYNTHETIC'},
                               repeat={'times':None,'completed':7})
        next_run=datetime.fromtimestamp(time.time()+86400,ZoneInfo('America/New_York')).replace(hour=5,minute=0,second=0,microsecond=0).isoformat()
        job=json.loads(t.reverse_schedule(p.stage.encoded(source),p.stage.encoded(native),next_run))['jobs'][0]
        self.assertEqual(job['id'],'same-id'); self.assertEqual(job['script'],'NAS-ORIGINAL.sh'); self.assertEqual(job['workdir'],'/NAS/notes')
        self.assertEqual(job['last_status'],'delivery_failed'); self.assertEqual(job['last_run_at'],'SYNTHETIC LATEST')
        self.assertEqual(job['repeat']['completed'],7); self.assertNotIn('fire_claim',job); self.assertEqual(job['next_run_at'],next_run)
        with self.assertRaises(ValueError): t.reverse_schedule(p.stage.encoded(source),p.stage.encoded(native),'2020-01-01T05:00:00-05:00')
        source['jobs'][0]['schedule']['display']='0 5 * * *';native['jobs'][0]['schedule']['display']='0 5 * * *'
        job=json.loads(t.reverse_schedule(p.stage.encoded(source),p.stage.encoded(native),next_run))['jobs'][0]
        self.assertEqual(job['schedule'],source['jobs'][0]['schedule'])
        for wrong in [dict(native['jobs'][0]['schedule'],display='0 6 * * *'),
                      dict(native['jobs'][0]['schedule'],expr='0 6 * * *'),
                      dict(native['jobs'][0]['schedule'],timezone='UTC')]:
            bad=copy.deepcopy(native);bad['jobs'][0]['schedule']=wrong
            with self.assertRaisesRegex(ValueError,'identity/history'):
                t.reverse_schedule(p.stage.encoded(source),p.stage.encoded(bad),next_run)
            both=copy.deepcopy(source);both['jobs'][0]['schedule']=wrong
            with self.assertRaisesRegex(ValueError,'identity/history'):
                t.reverse_schedule(p.stage.encoded(both),p.stage.encoded(bad),next_run)
        native['jobs'][0]['id']='FORKED'
        with self.assertRaisesRegex(ValueError,'identity/history'): t.reverse_schedule(p.stage.encoded(source),p.stage.encoded(native),next_run)

    def test_reverse_approved_payload_is_not_rewritten_to_refresh_stopped_proof(self):
        bundle=self.cold(); payload,approval=self.incident(bundle)
        payload['nativeStopped']=dict(payload['nativeStopped'],observedAt=time.time()-300)
        approval['reversePayloadSha256']=p.stage.digest(p.stage.encoded(payload))
        approved=p.stage.encoded(payload); before={n:p.signature(self.source/n) for n in t.selected_names(self.source)[0]}
        proof={'mainPID':0,'activeState':'inactive','ownershipPhase':'STOPPED_REVIEW_REQUIRED','observedAt':time.time()}
        with self.assertRaisesRegex(ValueError,'stopped-native'):
            t.apply_reverse(payload,self.source,self.root/'reverse-no-proof',approval)
        with self.assertRaisesRegex(ValueError,'stopped-native'):
            t.apply_reverse(payload,self.source,self.root/'reverse-stale-proof',approval,
                            current_native_proof=dict(proof,observedAt=time.time()-300))
        self.assertEqual(before,{n:p.signature(self.source/n) for n in before})
        result=t.apply_reverse(payload,self.source,self.root/'reverse-current-proof',approval,current_native_proof=proof)
        self.assertEqual(result['reverse'],'PASS'); self.assertEqual(p.stage.encoded(payload),approved)
        self.assertNotIn('observedAt',approval)

    def test_forward_selects_only_codex_retains_original_auth_cas(self):
        before=p.signature(self.source/'auth.json'); bundle=self.cold(); data=t.decode_bundle(bundle)
        auth=json.loads(data['auth.json'])
        self.assertEqual(set(auth['credential_pool']),{'openai-codex'})
        self.assertEqual(bundle['receipt']['sourceFiles']['auth.json'],before)
        self.assertNotEqual(bundle['receipt']['files']['auth.json']['sha256'],before['sha256'])
        self.assertEqual(p.signature(self.source/'auth.json'),before)
        self.assertNotIn(b'SYNTHETIC-UNRELATED',data['auth.json'])

    def test_integrated_seven_store_import_closed_schedule_and_exact_repeat(self):
        bundle=self.cold(); before={n:p.signature(self.source/n) for n in bundle['receipt']['sourceFiles']}
        result=t.import_bundle(bundle,self.m); self.assertEqual(result['databases'],7)
        state=Path(self.m['paths']['state'])
        jobs=json.loads((state/'cron/jobs.json').read_bytes())['jobs']
        self.assertEqual(len(jobs),1); self.assertFalse(jobs[0]['enabled']); self.assertIsNone(jobs[0]['deliver'])
        self.assertEqual(jobs[0]['workdir'],str(state/'workspace/notes'))
        receipt=t.load(state/'controller/import.json')
        signatures=copy.deepcopy(receipt['files'])
        self.assertEqual(t.import_bundle(bundle,self.m)['changedFiles'],0)
        self.assertEqual(t.load(state/'controller/import.json')['files'],signatures)
        self.assertEqual(before,{n:p.signature(self.source/n) for n in before})
        self.assertEqual(json.loads((state/'auth.json').read_bytes())['active_provider'],'openai-codex')

    def test_production_read_plugins_preserve_minimal_child_environment(self):
        bundle=self.cold(); t.import_bundle(bundle,self.m)
        state=Path(self.m['paths']['state']); vault=state/'workspace/notes'; vault.mkdir(mode=0o700)
        env={'HERMES_NATIVE_STAGE':'production','HERMES_NATIVE_READONLY':'1','HERMES_NATIVE_OFFLINE':'0',
             'HERMES_HOME':str(state),'VAULT_DIR':str(vault),'HERMES_NATIVE_MISE':'/nix/store/SYNTHETIC/bin/mise',
             'TELEGRAM_BOT_TOKEN':'SYNTHETIC-NOT-FOR-CHILD','OPENAI_API_KEY':'SYNTHETIC-NOT-FOR-CHILD'}
        for name,request,handler in [('macros','2026-10-10 dinner','_handle_macros'),('search','food synthetic','_handle_search')]:
            with mock.patch.dict(os.environ,env,clear=True):
                plugin=module('SYNTHETIC_production_'+name,state/('plugins/'+name+'/__init__.py'))
                process=mock.AsyncMock(return_value=(0,b'SYNTHETIC REPORT',b''))
                with mock.patch.object(plugin,'_run_process',process):
                    result=asyncio.run(getattr(plugin,handler)(request))
            self.assertIn('SYNTHETIC REPORT',result)
            child=process.call_args.kwargs['env']
            self.assertEqual(child['HERMES_NATIVE_STAGE'],'production')
            self.assertEqual(child['HERMES_NATIVE_READONLY'],'1')
            self.assertNotIn('TELEGRAM_BOT_TOKEN',child); self.assertNotIn('OPENAI_API_KEY',child)

    def test_unknown_queue_link_and_stale_source_refused(self):
        (self.source/'pending').mkdir(mode=0o700)
        self.write(self.source,'pending/uncertain.json',{'fixture':'SYNTHETIC UNKNOWN'})
        with self.assertRaisesRegex(ValueError,'queued'): self.cold()
        (self.source/'pending/uncertain.json').unlink()
        (self.source/'SOUL.md').unlink(); (self.source/'SOUL.md').symlink_to(self.source/'auth.json')
        with self.assertRaisesRegex(ValueError,'symlink'): self.cold()
        (self.source/'SOUL.md').unlink(); self.write(self.source,'SOUL.md',b'SYNTHETIC')
        bundle=self.cold(); bundle['sourceProof']['observedAt']=time.time()-121
        with self.assertRaisesRegex(ValueError,'fresh'): t.import_bundle(bundle,self.m)

    def test_reverse_latest_history_rotating_auth_unrelated_pool_and_noop(self):
        bundle=self.cold(); payload,approval=self.incident(bundle)
        evidence=self.root/'reverse'
        result=t.apply_reverse(payload,self.source,evidence,approval)
        self.assertEqual(result['reverse'],'PASS')
        auth=t.load(self.source/'auth.json')
        self.assertEqual(auth['credential_pool']['openai-api'],self.auth['credential_pool']['openai-api'])
        self.assertEqual(auth['providers']['openai-codex']['tokens']['refresh_token'],'SYNTHETIC-LATEST-REFRESH')
        c=sqlite3.connect(self.source/'state.db')
        self.assertEqual(c.execute('SELECT count(*) FROM messages').fetchone()[0],2)
        self.assertEqual(c.execute('SELECT count(*) FROM delivery_obligations').fetchone()[0],2); c.close()
        before={n:p.signature(self.source/n) for n in payload['files']}
        self.assertEqual(t.apply_reverse(payload,self.source,evidence,approval)['changedFiles'],0)
        self.assertEqual(before,{n:p.signature(self.source/n) for n in before})
        self.assertEqual(t.load(self.source/'config.yaml')['_config_version'],44)
        self.assertTrue(t.load(self.source/'cron/jobs.json')['jobs'][0]['enabled'])

    def test_reverse_wal_retained_preimage_and_removed_before_resume(self):
        c=sqlite3.connect(self.source/'state.db'); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA wal_autocheckpoint=0')
        c.execute("INSERT INTO messages VALUES(2,'public-fixture-session','SYNTHETIC SOURCE WAL')"); c.commit()
        try:
            bundle=self.cold(); self.assertIn('state.db-wal',bundle['receipt']['sourceFiles'])
            payload,approval=self.incident(bundle); evidence=self.root/'reverse'
            old_wal=(self.source/'state.db-wal').read_bytes()
            t.apply_reverse(payload,self.source,evidence,approval)
            self.assertEqual((evidence/'sidecar-preimages/state.db-wal').read_bytes(),old_wal)
            self.assertFalse((self.source/'state.db-wal').exists())
            self.assertFalse((self.source/'state.db-shm').exists())
            check=sqlite3.connect(self.source/'state.db')
            self.assertEqual(check.execute('SELECT count(*) FROM messages').fetchone()[0],3); check.close()
        finally: c.close()

    def test_reverse_requires_exact_approval_stopped_native_and_unchanged_source(self):
        bundle=self.cold(); payload,approval=self.incident(bundle)
        with self.assertRaisesRegex(ValueError,'approval'): t.apply_reverse(payload,self.source,self.root/'reverse',{})
        altered=copy.deepcopy(payload); altered['nativeStopped']['mainPID']=9
        with self.assertRaisesRegex(ValueError,'approval'): t.apply_reverse(altered,self.source,self.root/'reverse',approval)
        self.write(self.source,'auth.json',{'fixture':'SYNTHETIC NAS DIVERGENCE'})
        with self.assertRaisesRegex(ValueError,'diverged'): t.apply_reverse(payload,self.source,self.root/'reverse',approval)
        self.assertFalse((self.root/'reverse').exists())


class CalendarBroker(unittest.TestCase):
    ACCOUNT='jallen7usa@gmail.com'

    def request(self, text):
        return r.terminal_request({'command':'mise run '+text})

    def test_original_calendar_reads_aliases_and_approved_write_routes(self):
        for action in ['events','list','ls','event','get','info','show','raw','freebusy','conflicts','search','calendars','colors','time']:
            tail=' primary event-id' if action in {'event','get','info','show','raw'} else ''
            value=self.request('gog -- cal '+action+tail+' -a '+self.ACCOUNT+' -j --wrap-untrusted')
            self.assertEqual(value['operation'],'read')
            self.assertEqual(value['args'][0],'calendar')
        for action in ['create','add','new','update','edit','set','delete','rm','del','remove','respond','rsvp','reply']:
            tail=' primary' if action in {'create','add','new'} else ' primary event-id'
            self.assertEqual(self.request('gog -- calendar '+action+tail+' --account='+self.ACCOUNT)['operation'],'calendar-write')
        for command in ['get-calendar -- --format=plain','get-calendar -- --format=json','gog -- auth list --check --json',
                        'gog -- config get keyring_backend']:
            self.assertEqual(self.request(command)['operation'],'read')
        value=self.request('gog -- -a '+self.ACCOUNT+' cal events --today')
        self.assertEqual(value['args'],['--account='+self.ACCOUNT,'calendar','events','--today'])

    def test_no_blanket_tasks_non_calendar_administration_or_policy_escapes(self):
        rejected=['gog -- gmail labels list','gog -- drive search query','gog -- api calendar events',
                  'gog -- auth add '+self.ACCOUNT,'gog -- auth export','gog -- config get token',
                  'gog -- cal acl primary','gog -- cal subscribe primary','gog -- cal move primary id target',
                  'gog -- cal events','gog -- cal events -a auto','gog -- cal events -a other@example.com',
                  'gog -- cal events -a '+self.ACCOUNT+' --home=/tmp/alternate',
                  'gog -- cal events -a '+self.ACCOUNT+' --access-token=secret',
                  'gog -- cal events -a '+self.ACCOUNT+' --client=alternate',
                  'gog -- cal events -a '+self.ACCOUNT+' --enable-commands-exact=gmail.send',
                  'gog -- cal events -a '+self.ACCOUNT+' --readonly=false',
                  'gog -- cal events -a '+self.ACCOUNT+' --account='+self.ACCOUNT,
                  'gog -- cal create -a '+self.ACCOUNT,'gog -- cal delete primary -a '+self.ACCOUNT,
                  'get-calendar -- --input-file=/tmp/injected','get-calendar -- --format=telegram',
                  'gog-auth-bootstrap','morning-brief','update-system','gog -- auth list --check && env']
        for command in rejected:
            with self.subTest(command=command), self.assertRaises(ValueError): self.request(command)
        with self.assertRaises(ValueError):
            r.terminal_request({'command':'mise run gog -- auth list','background':True})

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name).resolve(); self.root.chmod(0o700)
        self.state=self.root/'state'; self.vault=self.root/'vault'
        for path in [self.state/'controller',self.state/'gogcli/data/keyring',self.vault/'.mise/tasks']:
            p.stage.mkdir(path)
        self.wrapper=b'#!/usr/bin/env bash\nset -eu\ntest "$GOG_KEYRING_BACKEND" = file\ntest "$GOG_KEYRING_PASSWORD" = SYNTHETIC\ntest -z "${PI_CODING_AGENT_DIR:-}"\ntest -z "${TELEGRAM_BOT_TOKEN:-}"\ncase "$GOG_READONLY" in 0) [[ "$GOG_ENABLE_COMMANDS_EXACT" == *calendar.create* ]] ;; 1) [[ "$GOG_ENABLE_COMMANDS_EXACT" != *calendar.create* ]] ;; *) exit 64 ;; esac\nif touch "$VAULT_DIR/must-not-write" 2>/dev/null; then exit 64; fi\nprintf \'{"fixture":"calendar-only","readonly":"%s"}\\n\' "$GOG_READONLY"\n'
        p.stage.atomic(self.vault/'.mise/tasks/gog',self.wrapper); (self.vault/'.mise/tasks/gog').chmod(0o700)
        p.stage.atomic(self.vault/'.mise/tasks/get-calendar',self.wrapper); (self.vault/'.mise/tasks/get-calendar').chmod(0o700)
        p.stage.atomic(self.state/'gogcli/config.json',b'{"synthetic":true}\n')
        p.stage.atomic(self.state/'gogcli/data/keyring/.lock',b'SYNTHETIC LOCK\n')
        p.stage.atomic(self.state/'.secrets.json',p.stage.encoded({'GOG_KEYRING_PASSWORD':'SYNTHETIC'}))
        p.stage.atomic(self.state/'controller/ownership.json',p.stage.encoded({'schemaVersion':1,'namespace':t.NAMESPACE,
            'owner':'native','phase':'NATIVE_LIVE','poller':'ENABLED'}))
        p.stage.atomic(self.state/'controller/task-code.json',p.stage.encoded({'kind':'REVIEWED_USER_OWNED_VAULT_TASK_CODE',
            'namespace':t.NAMESPACE,'files':{'.mise/tasks/get-calendar':p.stage.digest(self.wrapper)}}))
        self.patch=mock.patch.object(r,'CALENDAR_WRAPPER_SHA256',p.stage.digest(self.wrapper)); self.patch.start()
        self.m={'paths':{'state':str(self.state)},'vault':str(self.vault),'environment':{
            'PATH':'/synthetic','HERMES_NATIVE_MISE':'/synthetic/mise','PI_CODING_AGENT_DIR':'/never-mounted',
            'TELEGRAM_BOT_TOKEN':'SYNTHETIC_FORBIDDEN','GOG_ACCESS_TOKEN':'SYNTHETIC_FORBIDDEN'},
            'bubblewrap':'/synthetic/bwrap','envBinary':'/synthetic/env','bashBinary':'/synthetic/bash'}

    def tearDown(self):
        self.patch.stop(); self.tmp.cleanup()

    def test_runner_readonly_private_keyring_and_foreground_write_boundary(self):
        before={str(q):p.signature(q) for q in (self.state/'gogcli').rglob('*') if q.is_file()}
        args=['cal','create','primary','-a',self.ACCOUNT,'--summary','Synthetic fixture','--from','2030-01-01T10:00:00-05:00',
              '--to','2030-01-01T11:00:00-05:00']
        with mock.patch.object(r.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'{}\n',stderr=b'')) as run:
            r.read_task(self.m,'get-calendar',['--format=plain'])
            call=run.call_args; self.assertEqual(call.kwargs['env']['GOG_READONLY'],'1')
            self.assertNotIn('calendar.create',call.kwargs['env']['GOG_ENABLE_COMMANDS_EXACT'])
            self.assertNotIn('GOG_ACCESS_TOKEN',call.kwargs['env']); self.assertNotIn('TELEGRAM_BOT_TOKEN',call.kwargs['env'])
            argv=call.args[0]; self.assertIn('--ro-bind',argv); self.assertIn('--share-net',argv)
            private=Path(argv[argv.index('--bind')+1]); self.assertNotEqual(private,self.state/'gogcli')
            self.assertFalse((private/'data/keyring/.lock').exists())
            with self.assertRaisesRegex(ValueError,'background'): r.read_task(self.m,'gog',args)
            r.calendar_task(self.m,'gog',args,allow_write=True)
            self.assertEqual(run.call_args.kwargs['env']['GOG_READONLY'],'0')
            self.assertEqual(t.load(self.state/'controller/calendar-write.json')['status'],'COMPLETE')
        self.assertEqual(before,{str(q):p.signature(q) for q in (self.state/'gogcli').rglob('*') if q.is_file()})

    def test_actual_supervisor_broker_dispatches_reads_and_foreground_writes_only(self):
        self.m.update(runtimeEngineeringReady=True)
        self.m['paths']['home']=str(self.root/'home')
        owner=t.load(self.state/'controller/ownership.json'); owner['providerRefresh']='ENABLED'
        p.stage.atomic(self.state/'controller/ownership.json',p.stage.encoded(owner))
        p.stage.atomic(self.state/'controller/arming.json',p.stage.encoded({'namespace':t.NAMESPACE,'status':'ARMED','sourceBundleSha256':'SYNTHETIC'}))
        p.stage.atomic(self.state/'controller/import.json',p.stage.encoded({'sourceBundleSha256':'SYNTHETIC'}))
        for text in ['get-calendar -- --format=plain','gog -- cal events -a '+self.ACCOUNT,
                     'gog -- cal create primary -a '+self.ACCOUNT+' --summary Synthetic']:
            request=self.request(text); replies=[]
            def frame(connection,value=None):
                if value is None: return request
                replies.append(value)
            process=mock.Mock(); process.poll.side_effect=[None,0,0]; process.wait.return_value=0
            with mock.patch.object(r,'gateway_command',return_value=['/synthetic/gateway']), \
                 mock.patch.object(r,'local_writer_callbacks',return_value=(mock.Mock(),mock.Mock())), \
                 mock.patch.object(r,'broker_frame',side_effect=frame), \
                 mock.patch.object(r.subprocess,'Popen',return_value=process), \
                 mock.patch.object(r,'calendar_task',return_value=b'SYNTHETIC') as task:
                r._gateway_owned(self.m)
                self.assertEqual(replies,[{'status':'OK','output':'SYNTHETIC'}])
                self.assertEqual(task.call_args.kwargs.get('allow_write',False),request['operation']=='calendar-write')

    def test_failed_external_write_is_retained_and_never_retried(self):
        args=['calendar','delete','primary','synthetic-id','-a',self.ACCOUNT]
        with mock.patch.object(r.subprocess,'run',side_effect=subprocess.TimeoutExpired('SYNTHETIC',1)) as run:
            with self.assertRaises(subprocess.TimeoutExpired): r.calendar_task(self.m,'gog',args,allow_write=True)
            self.assertEqual(t.load(self.state/'controller/calendar-write.json')['status'],'CLAIMED')
            with self.assertRaisesRegex(ValueError,'uncertain'): r.calendar_task(self.m,'gog',args,allow_write=True)
            self.assertEqual(run.call_count,1)
        (self.vault/'.mise/tasks/gog').write_bytes(b'UNREVIEWED')
        with self.assertRaisesRegex(ValueError,'unchanged'): r.read_task(self.m,'gog',['auth','list'])

    @unittest.skipUnless(os.environ.get('HERMES_CALENDAR_FIXTURE_METADATA'),'installed Linux bubblewrap fixture only')
    def test_actual_bubblewrap_runner_synthetic_reads_and_writes_no_api(self):
        installed=json.loads(Path(os.environ['HERMES_CALENDAR_FIXTURE_METADATA']).read_bytes())
        self.m.update({k:installed[k] for k in ['bubblewrap','envBinary','bashBinary']})
        self.m['environment']=dict(installed['environment'])
        for task,args,write in [('get-calendar',['--format=plain'],False),
            ('gog',['cal','events','-a',self.ACCOUNT,'--today'],False),
            ('gog',['cal','create','primary','-a',self.ACCOUNT,'--summary','Synthetic'],True)]:
            output=r.calendar_task(self.m,task,args,allow_write=write)
            self.assertEqual(json.loads(output),{'fixture':'calendar-only','readonly':'0' if write else '1'})
        self.assertFalse((self.vault/'must-not-write').exists())


@unittest.skipUnless(os.environ.get('HERMES763_TASK_SOURCES') and sys.platform=='linux',
                     'operator-provided reviewed code + pinned Linux sandbox fixture')
class ActualTaskAdapter(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='hermes763-actual-adapter-')
        self.root=Path(self.tmp.name)
        state=self.root/'hermes-native/production/baseline-0.21.2'; state.mkdir(parents=True,mode=0o700)
        vault=self.root/'vault'; vault.mkdir(mode=0o700)
        for n in ['journal','templates','lists','health','recipes','.mise/tasks','scripts','.obsidian']:
            (vault/n).mkdir(parents=True,mode=0o700,exist_ok=True)
        m=json.loads(Path('/home/johna/.config/hermes-native/production.json').read_bytes())
        m['paths']['state']=str(state); m['vault']=str(vault)
        # Execution assets stay the ACTUAL immutable installed closure. Mutable
        # fixture code supplies the outer controller only, not a /tmp script
        # hidden by the child's private /tmp namespace.
        m['environment']=dict(m['environment'],HERMES_HOME=str(state))
        path=m['environment']['PATH'].split(':')
        m['envBinary']=next(q+'/env' for q in path if Path(q+'/env').is_file())
        m['bashBinary']=next(q+'/bash' for q in path if Path(q+'/bash').is_file())
        # The immutable new task shims are tested after HM installation. This
        # fixture only uses the host's currently installed pinned dependency closure.
        self.m,self.state,self.vault=m,state,vault
        for n in ['home','config','cache']:
            q=self.root/n; q.mkdir(mode=0o700); m['paths'][n]=str(q)
        r.initialize(m)
        owner=t.load(state/'controller/ownership.json')
        owner.update(owner='native',phase='NATIVE_LIVE',vaultWrites='ENABLED',
                     normalWriterPolicy='NAS_NORMAL_NONOVERLAP_POLICY_CONTINUATION')
        p.stage.atomic(state/'controller/ownership.json',p.stage.encoded(owner))
        source=Path(os.environ['HERMES763_TASK_SOURCES'])
        hashes=json.loads((source/'hashes.json').read_bytes())
        for n,sha in hashes.items():
            p.relative(n); data=p.stage.read_private(source/n,owner=os.getuid())
            self.assertEqual(p.stage.digest(data),sha)
            p.stage.atomic(vault/n,data); (vault/n).chmod(0o700)
        self.hashes=hashes
        self.ledger()
        self.today=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
        self.relative='journal/'+self.today+'.md'
        template=('# '+self.today+'\n\n## Tasks\n\n- [ ] KEEP TASK\n\n## Misc\n\nKEEP MISC\n\n'
                  '## Nutrition\n\n### Daily Totals\n\n### Nutrition Log\n\n> [!note]- Raw nutrition entries\n>\n'
                  '### Nutrition Summary\n\n![[nutrition-summary]]\n\n## Activity\n\n'
                  '### Activity Log\n\n> [!note]- Raw activity entries\n>\n### Activity Summary\n\n'
                  '![[activity-summary]]\n\n## Captures\n\nKEEP CAPTURE\n\n## Pi Log\n\nKEEP LOG\n')
        p.stage.atomic(vault/self.relative,template.encode())
        p.stage.atomic(vault/'templates/journal.md',template.encode())
        p.stage.atomic(vault/'journal/untouched.md',b'SYNTHETIC UNTOUCHED SIBLING\n')
        for n in ['tasks','shopping','groceries']: p.stage.atomic(vault/('lists/'+n+'.md'),b'# Synthetic\n\nKEEP LIST\n')
        self.calls=0

    def tearDown(self): self.tmp.cleanup()

    def ledger(self):
        p.stage.atomic(self.state/'controller/task-code.json',p.stage.encoded({
            'kind':'REVIEWED_USER_OWNED_VAULT_TASK_CODE','namespace':t.NAMESPACE,'files':self.hashes}))

    def observation(self,names):
        self.calls+=1
        return {'folder':'notes','type':'sendreceive','state':'idle','observedAt':time.time(),
                'localConvergence':True,'directPeerConvergence':True,'directPeerCount':1,
                'conflicts':0,'temporary':0,'special':0}

    def task(self,name,args):
        try:
            return r.sandboxed_task(self.m,name,args,observer=self.observation,scan=lambda names:None)
        except ValueError:
            # Fixture state contains synthetic data only. Live adapter failures
            # never echo the retained child stderr or task arguments.
            failures=sorted((self.state/'controller/task-runs').glob('*/stderr'),key=lambda path:path.stat().st_mtime_ns)
            if failures: print('SYNTHETIC CHILD DIAGNOSTIC',failures[-1].read_text()[-1500:])
            raise

    def test_actual_food_task_private_postimage_commit_retry_and_sibling_preservation(self):
        args=['--date',self.today,'--meal','dinner','--food','synthetic-fixture','--amount','1','--unit','serving',
              '--calories','250','--protein-g','20','--carbs-g','30','--fat-g','8','--fiber-g','4','--source','common']
        self.task('write-food-log',args)
        text=(self.vault/self.relative).read_text()
        self.assertEqual(text.count('[food:: synthetic-fixture]'),1)
        self.assertIn('KEEP LOG',text); self.assertIn('nutrition_calories:: 250',text)
        before=p.signature(self.vault/self.relative)
        self.task('write-food-log',args)
        self.assertEqual(p.signature(self.vault/self.relative),before)
        self.assertEqual((self.vault/'journal/untouched.md').read_bytes(),b'SYNTHETIC UNTOUCHED SIBLING\n')
        self.assertGreater(self.calls,4)
        record=t.load(self.state/'writer-reservation.json')
        self.assertEqual(record['status'],'COMPLETE'); self.assertNotIn('confirmedAt',record)

    def test_actual_weight_activity_lists_and_food_correction_use_the_same_adapter(self):
        self.task('log-weight',['180.1'])
        before=p.signature(self.vault/self.relative)
        self.task('log-weight',['180.1'])
        self.assertEqual(p.signature(self.vault/self.relative),before)
        self.assertIn('weight:: 180.1',(self.vault/self.relative).read_text())
        self.task('activity-log',['--date',self.today,'--time','15:30','SYNTHETIC incline walk 5%, 30m, 3mph'])
        self.assertIn('SYNTHETIC incline walk',(self.vault/self.relative).read_text())
        self.task('add-list-item',['SYNTHETIC shopping item','shopping'])
        self.assertIn('SYNTHETIC shopping item',(self.vault/'lists/shopping.md').read_text())
        before=p.signature(self.vault/'lists/shopping.md')
        self.task('add-list-item',['SYNTHETIC shopping item','shopping'])
        self.assertEqual(p.signature(self.vault/'lists/shopping.md'),before)
        self.task('add-list-item',['SYNTHETIC daily reminder','daily','--date','2030-01-01'])
        self.assertIn('SYNTHETIC daily reminder',(self.vault/self.relative).read_text())
        self.assertFalse((self.vault/'journal/2030-01-01.md').exists())
        macros=['--date',self.today,'--meal','dinner','--food','synthetic-fixture','--amount','1','--unit','serving',
                '--calories','250','--protein-g','20','--carbs-g','30','--fat-g','8','--fiber-g','4','--source','common']
        self.task('write-food-log',macros)
        changed=[*macros,'--match-food','synthetic-fixture']
        changed[changed.index('--calories')+1]='275'
        self.task('adjust-food-log',changed)
        text=(self.vault/self.relative).read_text()
        self.assertEqual(text.count('[food:: synthetic-fixture]'),1)
        self.assertIn('nutrition_calories:: 275',text); self.assertIn('KEEP CAPTURE',text)
        before=p.signature(self.vault/self.relative)
        self.task('adjust-food-log',changed)
        self.assertEqual(p.signature(self.vault/self.relative),before)

    def test_actual_pinned_browser_uv_and_recipe_renderer_without_download_or_model(self):
        p.stage.atomic(self.vault/'health/common-foods.yaml',p.stage.encoded({'foods':[{
            'id':'SYNTHETIC-food','name':'Synthetic Greek yogurt','category':'main-dishes',
            'serving':{'amount':1,'unit':'serving'},'nutrition':{'calories':250,'protein_g':20}}]}))
        # The existing user-owned renderer deliberately requires both its source
        # sentinel and a preexisting output note; do not weaken that guard.
        p.stage.atomic(self.vault/'health/common-foods-browser.html',b'<!doctype html><title>Synthetic fixture</title>')
        self.assertIn(b'Synthetic Greek yogurt',r.read_task(self.m,'common-food',['search','Greek']))
        self.assertIn(b'YAML OK',r.read_task(self.m,'common-food',['validate']))
        self.assertRegex(r.read_task(self.m,'date',['+%Y-%m-%d %H:%M:%S %Z (%z)']).decode(),
                         r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} E[DS]T \(-0[45]00\)\n$')
        self.task('common-foods-browser',[])
        self.assertIn('Synthetic Greek yogurt',(self.vault/'health/common-foods-browser.html').read_text())
        note='recipes/synthetic.md'
        p.stage.atomic(self.vault/note,b'# Synthetic recipe\n\n## Ingredients\n\n- 1 cup synthetic beans\n\n## Steps\n\n1. Stir synthetic beans.\n')
        plan={'row_order':[0],'columns':[{'label':'Mix','cells':[{
            'start':0,'end':0,'title':'Stir','detail':'Synthetic beans','steps':[1]}]}]}
        p.stage.atomic(self.vault/'recipes/synthetic-plan.json',p.stage.encoded(plan))
        self.task('recipe-table',[note,'--plan-file','recipes/synthetic-plan.json'])
        self.assertIn('recipe-table__ingredient',(self.vault/note).read_text())
        before=p.signature(self.vault/note)
        self.task('recipe-table',[note,'--plan-file','recipes/synthetic-plan.json'])
        self.assertEqual(p.signature(self.vault/note),before)

    def test_actual_canonical_recipe_create_update_and_common_food_upsert_without_generic_write(self):
        import yaml
        note='recipes/synthetic-canonical.md'
        markdown='# Synthetic recipe\n\n## Ingredients\n\n- 1 cup synthetic beans\n\n## Steps\n\n1. Stir synthetic beans.\n'
        plan={'row_order':[0],'columns':[{'label':'Mix','cells':[{
            'start':0,'end':0,'title':'Stir','detail':'Synthetic beans','steps':[1]}]}]}
        args=[note,json.dumps(markdown),json.dumps(plan)]
        request=r.terminal_request({'command':'mise run save-recipe -- '+__import__('shlex').join(args)})
        self.assertEqual(request,{'operation':'write','task':'save-recipe','args':args})
        self.task('save-recipe',args)
        self.assertIn('recipe-table__ingredient',(self.vault/note).read_text())
        self.task('save-recipe',[note,json.dumps(markdown.replace('1 cup','2 cups')),json.dumps(plan)])
        self.assertIn('2 cups',(self.vault/note).read_text())
        self.assertFalse((self.vault/'recipes/recipe-plan.json').exists())
        food={'id':'synthetic-food','name':'Synthetic Greek yogurt','category':'main-dishes',
              'serving':{'amount':1,'unit':'serving'},
              'nutrition':{'calories':250,'protein_g':20,'carbs_g':30,'fat_g':8},
              'recipe':note,'notes':'Synthetic disclosed estimate'}
        unrelated={'id':'keep','name':'Keep unrelated','nutrition':{'calories':12}}
        p.stage.atomic(self.vault/'health/common-foods.yaml',p.stage.encoded({
            'metadata':{'keep':True},'foods':[unrelated,{**food,'extraMetadata':'KEEP','nutrition':{**food['nutrition'],'fiber_g':4}}]}))
        p.stage.atomic(self.vault/'health/common-foods-browser.html',b'<!doctype html><title>Synthetic fixture</title>')
        self.task('save-common-food',[json.dumps(food)])
        food['nutrition']['calories']=275
        self.task('save-common-food',[json.dumps(food)])
        data=yaml.safe_load((self.vault/'health/common-foods.yaml').read_bytes())
        self.assertEqual(data['metadata'],{'keep':True}); self.assertEqual(data['foods'][0],unrelated)
        self.assertEqual(len(data['foods']),2); self.assertEqual(data['foods'][1]['extraMetadata'],'KEEP')
        self.assertEqual(data['foods'][1]['nutrition']['fiber_g'],4)
        self.assertEqual(data['foods'][1]['nutrition']['calories'],275)
        self.assertIn('Synthetic Greek yogurt',(self.vault/'health/common-foods-browser.html').read_text())
        self.assertEqual(t.load(self.state/'writer-reservation.json')['status'],'COMPLETE')
        self.assertNotIn('expiresAt',t.load(self.state/'writer-reservation.json'))

    def test_canonical_invalid_renderer_plan_preserves_real_recipe_and_retained_branch(self):
        note='recipes/synthetic-invalid.md'; original=b'SYNTHETIC ORIGINAL NOTE\n'
        p.stage.atomic(self.vault/note,original)
        markdown='# Synthetic\n\n## Ingredients\n\n- 1 cup beans\n\n## Steps\n\n1. Stir.\n'
        with self.assertRaisesRegex(ValueError,'reviewed task failed'):
            self.task('save-recipe',[note,json.dumps(markdown),json.dumps({'row_order':[999],'columns':[{}]})])
        self.assertEqual((self.vault/note).read_bytes(),original)
        self.assertEqual(t.load(self.state/'writer-reservation.json')['status'],'STOPPED_REVIEW_REQUIRED')
        self.assertTrue(list((self.state/'controller/task-runs').glob('*/recipe-plan.json')))

    def test_actual_brief_profile_symlink_is_not_mounted_and_other_symlinks_still_refuse(self):
        p.stage.atomic(self.vault/'AGENTS.md',b'SYNTHETIC PRIVATE PROFILE NOT TASK INPUT\n')
        profile=self.vault/'CLAUDE.md'; profile.symlink_to('AGENTS.md')
        identity=profile.lstat()
        self.test_actual_brief_orchestration_no_model_no_human_lease_stdout_only()
        after=profile.lstat()
        self.assertEqual((identity.st_dev,identity.st_ino,identity.st_mtime_ns,identity.st_ctime_ns),
                         (after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns))
        self.assertEqual(os.readlink(profile),'AGENTS.md')
        # An unrelated symlink is still refused before a child or vault commit.
        (self.vault/'unreviewed-link').symlink_to('AGENTS.md')
        before=p.signature(self.vault/self.relative)
        with mock.patch.object(r.subprocess,'run') as child:
            with self.assertRaisesRegex(ValueError,'symlink refused'):
                self.task('morning-brief',[])
            child.assert_not_called()
        self.assertEqual(p.signature(self.vault/self.relative),before)
        self.assertEqual(t.load(self.state/'writer-reservation.json')['status'],'STOPPED_REVIEW_REQUIRED')

    def test_actual_brief_orchestration_no_model_no_human_lease_stdout_only(self):
        for name,text in [('get-weather','SYNTHETIC clear 20 C'),('get-calendar','SYNTHETIC appointment 10:00')]:
            data=('#!/usr/bin/env bash\nset -eu\ntest ! -e "$VAULT_DIR/CLAUDE.md"\ntest ! -L "$VAULT_DIR/CLAUDE.md"\ntest "$GOG_READONLY" = 1\nmkdir -p "$GOG_HOME/data/keyring"\n: > "$GOG_HOME/data/keyring/.lock"\ncase "$*" in *--format=json*) printf \'{"fixture":true}\\n\';; *) printf \'%s\\n\' '+repr(text)+';; esac\n').encode()
            p.stage.atomic(self.vault/('.mise/tasks/'+name),data); (self.vault/('.mise/tasks/'+name)).chmod(0o700)
            self.hashes['.mise/tasks/'+name]=p.stage.digest(data)
        self.ledger()
        p.stage.mkdir(self.state/'gogcli')
        credential=self.state/'gogcli/config/synthetic-credential'
        p.stage.atomic(credential,b'SYNTHETIC GOOGLE CONTEXT NOT REAL\n'); google_before=p.signature(credential)
        p.stage.atomic(self.state/'.secrets.json',p.stage.encoded({'GOG_KEYRING_PASSWORD':'SYNTHETIC-NOT-REAL'}))
        output=self.task('morning-brief',[])
        self.assertEqual(p.signature(credential),google_before)
        self.assertFalse((self.state/'gogcli/data/keyring/.lock').exists())
        self.assertTrue(list((self.state/'controller/task-runs').glob('*/calendar-gogcli/data/keyring/.lock')))
        self.assertEqual(output.count(b'Good morning!'),1)
        self.assertIn(b'SYNTHETIC appointment',(self.vault/self.relative).read_bytes())
        before=p.signature(self.vault/self.relative)
        self.task('morning-brief',[])
        self.assertEqual(p.signature(self.vault/self.relative),before)
        self.assertEqual(t.load(self.state/'writer-reservation.json')['status'],'COMPLETE')
        self.assertNotIn('expiresAt',t.load(self.state/'writer-reservation.json'))

    def test_pinned_gateway_registry_scheduler_auth_and_slash_guards_offline(self):
        owner=t.load(self.state/'controller/ownership.json')
        owner.update(poller='ENABLED',providerRefresh='ENABLED',scheduler='ENABLED')
        p.stage.atomic(self.state/'controller/ownership.json',p.stage.encoded(owner))
        p.stage.atomic(self.state/'auth.json',p.stage.encoded({'active_provider':'openai-codex',
                     'providers':{'openai-codex':{'tokens':{'access_token':'SYNTHETIC'}}}}))
        env=dict(self.m['environment'],HOME=self.m['paths']['home'],HERMES_HOME=str(self.state))
        calls=[]
        def request(value): calls.append(value); return 'SYNTHETIC guarded output'
        with mock.patch.dict(os.environ,env,clear=True):
            import hermes_cli.auth_codex as codex
            from telegram.ext import Updater
            resolver=mock.Mock(return_value={'api_key':'SYNTHETIC-NOT-REAL'})
            polling=mock.AsyncMock(return_value=None)
            import cron.scheduler as dispatch
            tick=mock.Mock(return_value=1)
            with mock.patch.object(codex,'resolve_codex_runtime_credentials',resolver),mock.patch.object(Updater,'start_polling',polling),mock.patch.object(dispatch,'tick',tick):
                r.install_gateway_hooks(self.m,request)
                from tools.registry import registry
                result=json.loads(registry.get_entry('terminal').handler({'command':'mise run macros -- '+self.today}))
                self.assertEqual(result['exit_code'],0); self.assertEqual(calls[-1]['operation'],'read')
                count=len(calls)
                for command in ['touch /home/johna/notes/BAD','bash -c echo','mise run unknown','echo x > note','python3 arbitrary.py']:
                    self.assertEqual(json.loads(registry.get_entry('terminal').handler({'command':command}))['exit_code'],64)
                self.assertEqual(len(calls),count)
                import cron.scheduler_script as scheduler
                ok,text=scheduler._run_job_script_with_claim_heartbeat({'schedule':{'kind':'cron'}},'morning-brief.sh',
                    workdir=str(self.state/'workspace/notes'))
                self.assertTrue(ok); self.assertEqual(text,'SYNTHETIC guarded output')
                self.assertEqual(calls[-1],{'operation':'brief','task':'morning-brief','args':[]})
                self.assertFalse(scheduler._run_job_script('different.sh',workdir='/')[0])
                self.assertEqual(codex.resolve_codex_runtime_credentials()['api_key'],'SYNTHETIC-NOT-REAL')
                resolver.assert_called_once()
                import gateway.slash_access as access
                admin=access.SlashAccessPolicy(enabled=False,admin_user_ids=frozenset(),user_allowed_commands=frozenset())
                self.assertFalse(admin.can_run('SYNTHETIC','restart')); self.assertTrue(admin.can_run('SYNTHETIC','help'))
                actual=access.policy_for_source(None,SimpleNamespace(user_id='SYNTHETIC'))
                self.assertTrue(actual.enabled) # Pinned dispatcher cannot short-circuit it.
                for command in ['restart','reload_skills','reload_mcp','codex_runtime','proactive','hb','bp','suggest','debug',
                                'usage','kanban','platform','sethome','set-home','voice','topup']:
                    self.assertFalse(actual.can_run('SYNTHETIC',command))
                self.assertTrue(actual.can_run('SYNTHETIC','help'))
                from gateway.run_startup import GatewayStartupMixin
                resume=SimpleNamespace(_resume_pending_candidates=mock.Mock(side_effect=AssertionError('private replay')))
                self.assertEqual(GatewayStartupMixin._schedule_resume_pending_sessions(resume),0)
                self.assertEqual(GatewayStartupMixin._schedule_resume_pending_sessions(resume,platform='telegram'),0)
                resume._resume_pending_candidates.assert_not_called()
                self.assertNotIn('_kanban_dispatcher_watcher',GatewayStartupMixin._PRE_RECONNECT_WATCHERS)
                self.assertNotIn('_kanban_notifier_watcher',GatewayStartupMixin._PRE_RECONNECT_WATCHERS)
                self.assertIn('_session_housekeeping_watcher',GatewayStartupMixin._PRE_RECONNECT_WATCHERS)
                self.assertEqual(dispatch.tick(verbose=False),1); self.assertTrue(tick.call_args.kwargs['can_dispatch']())
                with r.scheduler_transition(self.m): self.assertEqual(dispatch.tick(),0)
                owner.update(phase='NATIVE_ARMED',scheduler='DISABLED')
                p.stage.atomic(self.state/'controller/ownership.json',p.stage.encoded(owner))
                self.assertEqual(dispatch.tick(),0); tick.assert_called_once()
                owner.update(phase='NATIVE_LIVE',scheduler='ENABLED')
                p.stage.atomic(self.state/'controller/ownership.json',p.stage.encoded(owner))
                asyncio.run(Updater.start_polling(None,drop_pending_updates=True))
                self.assertFalse(polling.call_args.kwargs['drop_pending_updates'])
                owner['providerRefresh']='DISABLED'; p.stage.atomic(self.state/'controller/ownership.json',p.stage.encoded(owner))
                with self.assertRaisesRegex(ValueError,'ownership'): codex.resolve_codex_runtime_credentials()
                resolver.assert_called_once()

    def supervisor_fixture(self):
        owner=t.load(self.state/'controller/ownership.json')
        owner.update(phase='NATIVE_ARMED',poller='ENABLED',providerRefresh='ENABLED',scheduler='DISABLED')
        p.stage.atomic(self.state/'controller/ownership.json',p.stage.encoded(owner))
        for name,data in [('arming.json',{'namespace':t.NAMESPACE,'status':'ARMED','sourceBundleSha256':'SYNTHETIC'}),
                          ('import.json',{'sourceBundleSha256':'SYNTHETIC'})]:
            p.stage.atomic(self.state/('controller/'+name),p.stage.encoded(data))
        p.stage.atomic(self.state/'.secrets.json',p.stage.encoded({'TELEGRAM_BOT_TOKEN':'SYNTHETIC-NOT-REAL'}))

    def test_outer_supervisor_actual_offline_child_exit_and_broker_refusal_revoke(self):
        import signal
        previous={sig:signal.getsignal(sig) for sig in (signal.SIGTERM,signal.SIGINT)}
        for exit_code in (0,75):
            self.supervisor_fixture()
            # The real outer supervisor owns its lifetime flock and socketpair;
            # only the child's upstream body is synthetic. No network namespace,
            # provider, bot, actual production state or user bus is available.
            code='''import json,os,socket,struct,sys
s=socket.socket(fileno=int(os.environ['HERMES_PRODUCTION_BROKER_FD']))
def exchange(value):
 b=json.dumps(value).encode(); s.sendall(struct.pack('!I',len(b))+b)
 def exact(n):
  b=b''
  while len(b)<n:
   chunk=s.recv(n-len(b)); assert chunk; b+=chunk
  return b
 return json.loads(exact(struct.unpack('!I',exact(4))[0]))
assert exchange({'operation':'read','task':'date','args':['+%F']})['status']=='REFUSED'
assert exchange({'operation':'write','task':'log-weight','args':['180.1']})['status']=='REFUSED'
s.close(); sys.exit(int(sys.argv[1]))
'''
            command=[self.m['bubblewrap'],'--unshare-all','--die-with-parent',
                     '--ro-bind','/nix/store','/nix/store','--proc','/proc','--dev','/dev','--tmpfs','/tmp',
                     self.m['python'],'-I','-B','-c',code,str(exit_code)]
            with mock.patch.object(r,'gateway_command',return_value=command), \
                 mock.patch.object(r,'local_writer_callbacks',return_value=(self.observation,lambda names:None)), \
                 mock.patch.object(r,'read_task',return_value=b'SYNTHETIC READ') as read, \
                 mock.patch.object(r,'sandboxed_task') as write:
                if exit_code:
                    with self.assertRaisesRegex(ValueError,'gateway exited'): r.gateway(self.m)
                else: r.gateway(self.m)
                read.assert_not_called(); write.assert_not_called()
            owner=t.load(self.state/'controller/ownership.json')
            self.assertEqual(owner['phase'],'STOPPED_REVIEW_REQUIRED')
            self.assertTrue(all(owner[k]=='DISABLED' for k in ['poller','providerRefresh','scheduler','vaultWrites']))
            self.assertEqual(previous,{sig:signal.getsignal(sig) for sig in previous})
            with r.writer_module().held_lock(self.state/'controller/runtime.lock'): pass

    def test_owned_supervisor_setup_failure_revokes_before_any_spawn(self):
        self.supervisor_fixture()
        (self.state/'.secrets.json').unlink()
        with mock.patch.object(r,'local_writer_callbacks',return_value=(self.observation,lambda names:None)), \
             mock.patch.object(r.subprocess,'Popen') as spawn:
            with self.assertRaises((OSError,ValueError)): r.gateway(self.m)
            spawn.assert_not_called()
        self.assertEqual(t.load(self.state/'controller/ownership.json')['phase'],'STOPPED_REVIEW_REQUIRED')

    def test_inherited_socketpair_is_available_inside_real_bwrap_without_listener(self):
        import socket,struct
        parent,child=socket.socketpair()
        process=None
        try:
            # Same descriptor strategy as the installed foreground supervisor.
            argv=[self.m['bubblewrap'],'--unshare-all','--die-with-parent',
                  '--ro-bind','/nix/store','/nix/store','--proc','/proc','--dev','/dev','--tmpfs','/tmp',
                  self.m['python'],'-I','-c','import socket,sys; s=socket.socket(fileno=int(sys.argv[1])); s.sendall(b"SYNTHETIC-FD"); assert s.recv(2)==b"OK"',str(child.fileno())]
            process=subprocess.Popen(argv,pass_fds=(child.fileno(),),stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd='/')
            child.close(); parent.settimeout(10)
            message=parent.recv(32)
            if message!=b'SYNTHETIC-FD':
                out,err=process.communicate(timeout=10)
                self.fail('SYNTHETIC bwrap descriptor: '+err.decode()[-1000:])
            parent.sendall(b'OK')
            out,err=process.communicate(timeout=10)
            self.assertEqual(process.returncode,0,err.decode()[-1000:])
        finally:
            parent.close(); child.close()
            if process and process.poll() is None: process.kill(); process.communicate(timeout=10)

    def test_complete_installed_gateway_child_namespace_and_hooks_without_network(self):
        import socket
        actual=json.loads(Path('/home/johna/.config/hermes-native/production.json').read_bytes())
        self.assertTrue(actual['runtimeEngineeringReady'])
        owner=t.load(self.state/'controller/ownership.json')
        owner.update(poller='ENABLED',providerRefresh='ENABLED',scheduler='DISABLED',phase='NATIVE_ARMED')
        p.stage.atomic(self.state/'controller/ownership.json',p.stage.encoded(owner))
        p.stage.atomic(self.state/'auth.json',p.stage.encoded({'active_provider':'openai-codex',
            'providers':{'openai-codex':{'tokens':{'access_token':'SYNTHETIC-NOT-REAL'}}}}))
        command=r.gateway_command(actual)
        command.remove('--share-net') # The engineering fixture never polls or calls providers.
        substitutions={actual['paths'][key]:self.m['paths'][key] for key in ['state','home','config','cache']}
        substitutions[actual['vault']]=str(self.vault)
        # Destinations and immutable installed metadata stay EXACT. Only host
        # mount sources are replaced with this disposable synthetic fixture.
        for i,token in enumerate(command):
            if token in {'--bind','--ro-bind'}:
                source=command[i+1]
                for original,replacement in substitutions.items():
                    if source==original or source.startswith(original+'/'):
                        command[i+1]=replacement+source[len(original):]; break
        code='''import importlib.util,os,pathlib,socket,errno,json
from unittest import mock
s=importlib.util.spec_from_file_location('installed_runtime',os.environ['HERMES_PRODUCTION_OPERATOR'])
r=importlib.util.module_from_spec(s); s.loader.exec_module(r)
m=r.t.native_metadata()
assert pathlib.Path('/usr/bin/env').is_file() and pathlib.Path('/bin/bash').is_file()
assert not pathlib.Path('/home/johna/.codex').exists() and not pathlib.Path('/run/user/1000/bus').exists()
path=pathlib.Path(m['paths']['state'])/'controller/ownership.json'
try:
 fd=os.open(path,os.O_WRONLY|os.O_NOFOLLOW)
except OSError as e: assert e.errno==errno.EROFS
else: os.close(fd); raise AssertionError('controller was writable')
import hermes_cli.auth_codex as codex
import gateway.run as upstream
resolver=mock.Mock(return_value={'api_key':'SYNTHETIC-NOT-REAL'})
def offline_main():
 from tools.registry import registry
 from gateway.slash_access import policy_for_source
 from types import SimpleNamespace
 import cron.scheduler as scheduler
 assert scheduler.tick(verbose=False)==0
 assert policy_for_source(None,SimpleNamespace(user_id='SYNTHETIC')).enabled
 result=json.loads(registry.get_entry('terminal').handler({'command':'date +%F'}))
 assert result['exit_code']==0 and result['output']=='SYNTHETIC BROKER READBACK'
 assert codex.resolve_codex_runtime_credentials()['api_key']=='SYNTHETIC-NOT-REAL'
with mock.patch.object(codex,'resolve_codex_runtime_credentials',resolver),mock.patch.object(upstream,'main',offline_main):
 r.gateway_child(m)
resolver.assert_called_once()
print('PASS immutable metadata/full namespace/pinned child hooks/RO controller/inherited IPC/no network')
'''
        parent,child=socket.socketpair(); process=None
        try:
            env=dict(actual['environment'],HERMES_PRODUCTION_BROKER_FD=str(child.fileno()))
            command=command[:-5]+[actual['python'],'-I','-B','-c',code]
            process=subprocess.Popen(command,env=env,pass_fds=(child.fileno(),),stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd='/')
            child.close(); parent.settimeout(30)
            try:
                request=r.broker_frame(parent)
                self.assertEqual(request,{'operation':'read','task':'date','args':['+%F']})
                r.broker_frame(parent,{'status':'OK','output':'SYNTHETIC BROKER READBACK'})
            except (EOFError,OSError):
                out,err=process.communicate(timeout=30)
                self.fail('SYNTHETIC full namespace: '+err.decode()[-1800:])
            out,err=process.communicate(timeout=30)
            self.assertEqual(process.returncode,0,err.decode()[-1800:])
            self.assertIn(b'PASS immutable metadata/full namespace',out)
        finally:
            parent.close(); child.close()
            if process and process.poll() is None: process.kill(); process.communicate(timeout=10)

    def test_real_namespace_cannot_write_sibling_or_see_host_profiles(self):
        data=b'#!/usr/bin/env bash\nset -eu\n[ ! -e /home/johna/.codex ]\n[ ! -e /home/johna/.config/claude-personal ]\nprintf BAD > "$VAULT_DIR/journal/untouched.md"\n'
        p.stage.atomic(self.vault/'.mise/tasks/activity-log',data); (self.vault/'.mise/tasks/activity-log').chmod(0o700)
        self.hashes['.mise/tasks/activity-log']=p.stage.digest(data); self.ledger()
        before=p.signature(self.vault/self.relative)
        with self.assertRaisesRegex(ValueError,'task failed'): self.task('activity-log',['--date',self.today,'walk'])
        self.assertEqual(p.signature(self.vault/self.relative),before)
        self.assertEqual((self.vault/'journal/untouched.md').read_bytes(),b'SYNTHETIC UNTOUCHED SIBLING\n')
        self.assertEqual(t.load(self.state/'writer-reservation.json')['status'],'STOPPED_REVIEW_REQUIRED')


if __name__=='__main__': unittest.main()
