import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import openapiTS, { astToString } from 'openapi-typescript'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontend, '..')
const python = process.env.PERFAGENT_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const result = spawnSync(python, ['-c', 'import json; from perfagent.api.app import app; print(json.dumps(app.openapi()))'], {
  cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONPATH: path.join(root, 'src'), PYTHONIOENCODING: 'utf-8' },
})
if (result.status !== 0) throw new Error('Could not export the API schema. Check PERFAGENT_PYTHON and Python dependencies.\n' + result.stderr)
const schema = JSON.parse(result.stdout)
const output = astToString(await openapiTS(schema, { defaultNonNullable: false }))
fs.mkdirSync(path.join(frontend, 'src/api'), { recursive: true })
fs.writeFileSync(path.join(frontend, 'src/api/schema.d.ts'), output)
console.log('Generated frontend/src/api/schema.d.ts from FastAPI OpenAPI')
