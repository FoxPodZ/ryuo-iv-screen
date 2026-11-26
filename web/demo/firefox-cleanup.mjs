// SPDX-License-Identifier: GPL-3.0-or-later
import {rm} from "node:fs/promises";

async function finishedWithin(event, milliseconds) {
  let timer;
  try {
    return await Promise.race([
      event.then(() => true),
      new Promise(resolve => { timer = setTimeout(() => resolve(false), milliseconds); }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

function releasePipes(child) {
  for (const pipe of [child.stdin, child.stdout, child.stderr]) {
    pipe?.destroy();
  }
}

export async function stopFirefox(child, closed, profile) {
  const hasExited = () => child.exitCode !== null || child.signalCode !== null;
  if (child.pid !== undefined && !hasExited()) {
    const exited = new Promise(resolve => child.once("exit", resolve));
    child.kill("SIGTERM");
    if (!await finishedWithin(exited, 5000) && !hasExited()) {
      child.kill("SIGKILL");
      if (!await finishedWithin(exited, 5000) && !hasExited()) {
        releasePipes(child);
        child.unref();
        throw new Error(`Firefox exit unconfirmed. Temporary profile retained at ${profile}`);
      }
    }
  }
  // A descendant can inherit a pipe and keep it open after the parent exits.
  if (!await finishedWithin(closed, 250)) releasePipes(child);
  await rm(profile, {recursive: true, force: true});
}
