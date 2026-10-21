// Verify native Pi skill selection without sessions, credentials, or model calls.
// node tests/implementation-attribution.mjs <runtime-root> [--installed]
// Installed mode respects the inherited PI_CODING_AGENT_DIR; run once per profile.
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, readFile, realpath, rm, writeFile} from 'node:fs/promises';
import {homedir, tmpdir} from 'node:os';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const runtime = process.argv[2];
assert(runtime, 'Explicit installed Pi runtime root required');
const {DefaultResourceLoader} = await import(pathToFileURL(join(runtime, 'dist/core/resource-loader.js')).href);
const {SettingsManager} = await import(pathToFileURL(join(runtime, 'dist/core/settings-manager.js')).href);
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = await readFile(join(root, 'modules/home-manager/agent-skills/authoring-commits/SKILL.md'), 'utf8');
const policy = await readFile(join(root, 'modules/home-manager/agent-projects/attribution-instructions.md'), 'utf8');

if (process.argv.includes('--installed')) {
  const profile = process.env.PI_CODING_AGENT_DIR;
  assert([join(homedir(), '.config/pi'), join(homedir(), '.config/pi-work')].includes(profile),
    'Keep the inherited personal or work profile explicit');
  const loader = new DefaultResourceLoader({
    cwd: root, agentDir: profile, noExtensions: true,
    settingsManager: SettingsManager.create(root, profile),
  });
  await loader.reload();
  const selected = loader.getSkills().skills.filter(skill => skill.name === 'authoring-commits');
  assert.equal(selected.length, 1);
  assert.equal(await readFile(selected[0].filePath, 'utf8'), source,
    'The native loader must select the canonical skill, not an agent-kit copy');
  assert((await realpath(selected[0].filePath)).startsWith('/nix/store/'));
  assert(loader.getAgentsFiles().agentsFiles.some(file => file.content.includes(policy)),
    'Native profile context must include the contributor attribution policy');
  console.log(`PASS installed native Pi discovery: ${profile}`);
} else {
  const tmp = await mkdtemp(join(tmpdir(), 'attribution-discovery-'));
  try {
    const profile = join(tmp, 'profile');
    const canonical = join(profile, 'skills/authoring-commits/SKILL.md');
    const packaged = join(tmp, 'package');
    const packagedSkill = join(packaged, 'skills/authoring-commits/SKILL.md');
    await mkdir(dirname(canonical), {recursive: true});
    await mkdir(dirname(packagedSkill), {recursive: true});
    await writeFile(canonical, source);
    await writeFile(packagedSkill, '---\nname: authoring-commits\ndescription: Conflicting packaged skill\n---\nCredit the cleanup model.\n');
    await writeFile(join(packaged, 'package.json'), JSON.stringify({name: 'attribution-fixture', pi: {skills: ['skills']}}));
    const loader = new DefaultResourceLoader({
      cwd: tmp, agentDir: profile, noExtensions: true,
      settingsManager: SettingsManager.inMemory({packages: [packaged]}),
    });
    await loader.reload();
    const selected = loader.getSkills().skills.find(skill => skill.name === 'authoring-commits');
    assert(selected);
    assert.equal(await realpath(selected.filePath), await realpath(canonical));
    assert.equal(await readFile(packagedSkill, 'utf8'), '---\nname: authoring-commits\ndescription: Conflicting packaged skill\n---\nCredit the cleanup model.\n');
    console.log('PASS native Pi precedence: canonical profile skill wins; packaged skill remains untouched');
  } finally {
    await rm(tmp, {recursive: true, force: true});
  }
}
