import { spawn } from 'node:child_process'
import { createWriteStream } from 'node:fs'
import { resolve } from 'node:path'

const commands = {
  dev: [['vite']],
  build: [['vue-tsc'], ['vite', 'build']],
  preview: [['vite', 'preview']]
}

const scriptName = process.argv[2]
const steps = commands[scriptName]

if (!steps) {
  console.error(`Unknown script: ${scriptName}`)
  process.exit(1)
}

const logFile = createWriteStream(resolve(process.cwd(), 'runtime.log'), {
  encoding: 'utf-8',
  flags: 'w'
})

function writeOutput(chunk, stream) {
  stream.write(chunk)
  logFile.write(chunk)
}

async function runStep([command, ...args]) {
  return new Promise((resolveStep) => {
    const child = spawn(command, args, {
      shell: true,
      stdio: ['inherit', 'pipe', 'pipe']
    })

    child.stdout.on('data', (chunk) => writeOutput(chunk, process.stdout))
    child.stderr.on('data', (chunk) => writeOutput(chunk, process.stderr))
    child.on('close', resolveStep)
  })
}

for (const step of steps) {
  const exitCode = await runStep(step)
  if (exitCode !== 0) {
    logFile.end(() => process.exit(exitCode ?? 1))
    await new Promise(() => {})
  }
}

logFile.end()
