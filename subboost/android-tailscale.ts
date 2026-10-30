import { dump, load } from "js-yaml";
import profile from "./android-tailscale.json";

export const ANDROID_TAILSCALE_PROFILE = "android-tailscale";
export const STASH_TAILSCALE_PROFILE = "stash-tailscale";
export const PHONE_TAILSCALE_PROFILE = "phone";
type TailscaleClient = "mihomo" | "stash";

export function subscriptionTailscaleClient(profile: string | null, userAgent: string | null): TailscaleClient | null {
  if (!profile) return null;
  if (profile === STASH_TAILSCALE_PROFILE) return "stash";
  if (profile !== ANDROID_TAILSCALE_PROFILE && profile !== PHONE_TAILSCALE_PROFILE) {
    throw new Error("Unknown subscription profile.");
  }
  return /\bstash\b/i.test(userAgent ?? "") ? "stash" : "mihomo";
}

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Add a phone-only overlay after SubBoost has generated its normal subscription. */
export function applyAndroidTailscaleProfile(yaml: string): string {
  return applyTailscaleProfile(yaml, "mihomo");
}

export function applyTailscaleProfile(yaml: string, client: TailscaleClient): string {
  const config = load(yaml);
  if (!record(config) || !Array.isArray(config.proxies) || !Array.isArray(config.rules)) {
    throw new Error("Phone Tailscale profile requires a generated Clash configuration.");
  }
  const groups = Array.isArray(config["proxy-groups"]) ? config["proxy-groups"] : [];
  if ([...config.proxies, ...groups].some((item) => record(item) && item.name === profile.name)) {
    throw new Error("Phone Tailscale profile has a reserved proxy name conflict.");
  }

  // Append after group generation, so normal select/url-test groups retain their candidates.
  config.proxies.push(client === "stash" ? {
    name: profile.name,
    type: "tailscale",
    // Let Stash report this Apple device's own hostname and persist its identity.
    "benchmark-disabled": true,
  } : {
    name: profile.name,
    type: "tailscale",
    hostname: profile.hostname,
    "state-dir": profile.stateDir,
    "accept-routes": true,
    ephemeral: false,
    udp: true,
  });
  // Future include-all groups must also exclude the private-network-only outbound.
  const escapedName = profile.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  for (const group of groups) {
    if (record(group) && (group["include-all"] === true || group["include-all-proxies"] === true)) {
      const existing = group["exclude-filter"];
      group["exclude-filter"] = existing ? `(?:${existing})|^${escapedName}$` : `^${escapedName}$`;
    }
  }

  // These must precede LAN DIRECT, process rules, GEOIP and MATCH.
  config.rules = [
    `DOMAIN-SUFFIX,${profile.tailnetDomain},${profile.name}`,
    `IP-CIDR,100.64.0.0/10,${profile.name},no-resolve`,
    `IP-CIDR6,fd7a:115c:a1e0::/48,${profile.name},no-resolve`,
    ...profile.homeSubnets.map((cidr) => `IP-CIDR,${cidr},${profile.name},no-resolve`),
    ...config.rules,
  ];
  config.mode = "rule";

  const dns = record(config.dns) ? config.dns : {};
  const policy = record(dns["nameserver-policy"]) ? dns["nameserver-policy"] : {};
  const tailnetPolicy = `+.${profile.tailnetDomain}`;
  // Remove equivalent exact/wildcard policies so the Tailnet resolver wins consistently.
  for (const key of [profile.tailnetDomain, `*.${profile.tailnetDomain}`, tailnetPolicy]) {
    delete policy[key];
  }
  // Stash resolves MagicDNS inside its Tailscale engine; ts:// is Mihomo-only.
  dns["nameserver-policy"] = client === "stash" ? policy : { [tailnetPolicy]: [`ts://${profile.name}`], ...policy };
  // A whitelist cannot be safely extended with a blacklist exclusion.
  const filter = Array.isArray(dns["fake-ip-filter"]) ? dns["fake-ip-filter"] : [];
  const whitelist = dns["fake-ip-filter-mode"] === "whitelist";
  if (whitelist) {
    throw new Error("Phone Tailscale profile requires a fake-IP blacklist.");
  }
  dns["fake-ip-filter"] = [...new Set([...filter, tailnetPolicy])];
  config.dns = dns;
  return dump(config, { noRefs: true, lineWidth: -1, quotingType: '"' });
}
