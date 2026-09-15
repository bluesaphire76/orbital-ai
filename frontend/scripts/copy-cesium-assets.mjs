import {
  cp,
  mkdir,
  rm,
} from "node:fs/promises";

import {
  dirname,
  join,
} from "node:path";

import {
  fileURLToPath,
} from "node:url";


const scriptDir = dirname(
  fileURLToPath(import.meta.url),
);

const root = join(
  scriptDir,
  "..",
);

const source = join(
  root,
  "node_modules",
  "cesium",
  "Build",
  "Cesium",
);

const target = join(
  root,
  "public",
  "cesium",
);


await rm(
  target,
  {
    recursive: true,
    force: true,
  },
);

await mkdir(
  target,
  {
    recursive: true,
  },
);


for (
  const directory
  of [
    "Workers",
    "ThirdParty",
    "Assets",
    "Widgets",
  ]
) {
  await cp(
    join(
      source,
      directory,
    ),
    join(
      target,
      directory,
    ),
    {
      recursive: true,
    },
  );
}


console.log(
  "Cesium static assets copied.",
);
