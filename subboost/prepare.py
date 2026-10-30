#!/usr/bin/env python3
"""Prepare a clean, pinned SubBoost build context; never read production credentials."""
import argparse
import io
import pathlib
import shutil
import tarfile
import urllib.request

UPSTREAM = "4a69b494b46d095c965be58cf425fe35a2c1e524"
HERE = pathlib.Path(__file__).resolve().parent


def replace_once(path, before, after):
    source = path.read_text()
    if source.count(before) != 1:
        raise RuntimeError("Pinned upstream patch no longer applies: " + str(path))
    path.write_text(source.replace(before, after, 1))


def prepare(destination):
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise RuntimeError("Build destination must be empty")
    url = "https://codeload.github.com/SubBoost/subboost/tar.gz/" + UPSTREAM
    data = urllib.request.urlopen(url, timeout=60).read()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            parts = pathlib.PurePosixPath(member.name).parts
            if len(parts) <= 1:
                continue
            if ".." in parts or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise RuntimeError("Unexpected archive entry")
            member.name = str(pathlib.PurePosixPath(*parts[1:]))
            archive.extract(member, destination)

    for filename in ("android-tailscale.ts", "android-tailscale.json", "android-tailscale.test.ts"):
        shutil.copy2(HERE / filename, destination / "local/src/lib" / filename)
    metadata = destination / "local/app/api/integrations/subscriptions/route.ts"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "subscriptions-metadata-route.ts", metadata)
    route = destination / "local/app/api/subscriptions/[id]/config.yaml/route.ts"
    replace_once(route, 'import { apiError } from "@local/lib/http";',
                 'import { apiError } from "@local/lib/http";\n'
                 'import { applyTailscaleProfile, subscriptionTailscaleClient } from "@local/lib/android-tailscale";')
    replace_once(route, '  return new Response(result.yaml, {',
                 '  let client: ReturnType<typeof subscriptionTailscaleClient>;\n'
                 '  try {\n'
                 '    client = subscriptionTailscaleClient(new URL(request.url).searchParams.get("profile"), request.headers.get("user-agent"));\n'
                 '  } catch { return apiError("Unknown subscription profile.", "BAD_REQUEST", 400); }\n'
                 '  let yaml = result.yaml;\n'
                 '  if (client) {\n'
                 '    try { yaml = applyTailscaleProfile(yaml, client); }\n'
                 '    catch { return apiError("Unable to generate phone Tailscale profile.", "CONFIGURATION_ERROR", 500); }\n'
                 '  }\n'
                 '  const headers = buildSubscriptionResponseHeaders(result.name, result.subscriptionInfo, {\n'
                 '    cacheControl: "no-store", cacheExpirySeconds: result.cacheExpirySeconds,\n'
                 '    autoUpdateIntervalSeconds: result.autoUpdateIntervalSeconds, isAdmin: result.isAdmin,\n'
                 '  });\n'
                 '  if (client) headers["vary"] = "User-Agent";\n'
                 '  return new Response(yaml, {')
    replace_once(route,
                 '    headers: buildSubscriptionResponseHeaders(result.name, result.subscriptionInfo, {\n'
                 '      cacheControl: "no-store",\n'
                 '      cacheExpirySeconds: result.cacheExpirySeconds,\n'
                 '      autoUpdateIntervalSeconds: result.autoUpdateIntervalSeconds,\n'
                 '      isAdmin: result.isAdmin,\n'
                 '    }),',
                 '    headers,')
    tests = destination / "local/app/api/subscriptions/[id]/config.yaml/route.test.ts"
    tests.write_text(tests.read_text() + '\n' + (HERE / "route-tests.ts.txt").read_text())
    # Limit Next build workers on the NAS; this does not change request handling.
    replace_once(destination / "local/next.config.mjs", '  output: "standalone",',
                 '  output: "standalone",\n  experimental: { cpus: 1 },')
    shutil.copy2(HERE / "Dockerfile", destination / "Dockerfile")
    print("Prepared pinned SubBoost source:", destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=pathlib.Path)
    prepare(parser.parse_args().destination.resolve())
