const { Socket } = require("node:net");
const dns = require("node:dns");

/**
 * Optional per-connection DNS fallback for networks that refuse *.neon.tech.
 * Only DNS lookup changes: the original hostname remains available for TLS/SNI.
 * @param {string} connectionString
 * @returns {import("pg").ClientConfig}
 */
function databaseConfig(connectionString) {
  const url = new URL(connectionString);
  if (url.searchParams.get("sslmode") === "require") url.searchParams.set("sslmode", "verify-full");
  const config = { connectionString: url.toString() };
  const servers = process.env.NEON_DNS_SERVERS?.split(",").map(s => s.trim()).filter(Boolean);
  if (!servers?.length || !url.hostname.endsWith(".neon.tech")) return config;
  const resolver = new dns.Resolver({ timeout: 3000, tries: 2 });
  resolver.setServers(servers);
  return {
    ...config,
    stream: () => {
      const socket = new Socket();
      const connect = socket.connect.bind(socket);
      socket.connect = (port, host) => connect({
        port, host,
        lookup: (hostname, options, callback) => {
          dns.lookup(hostname, options, (error, address, family) => {
            if (!error) return callback(null, address, family);
            resolver.resolve4(hostname, (fallbackError, addresses) => {
              if (fallbackError) return callback(fallbackError);
              if (options.all) return callback(null, addresses.map(value => ({ address: value, family: 4 })));
              callback(null, addresses[0], 4);
            });
          });
        },
      });
      return socket;
    },
  };
}
module.exports = { databaseConfig };
