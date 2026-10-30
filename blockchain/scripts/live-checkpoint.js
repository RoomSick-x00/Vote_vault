// Local-only signer setup for the live API checkpoint. Never prints/writes a key.
const hre = require("hardhat");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
async function main() {
  const manifest = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../deployments/localhost.json")));
  if ((await hre.ethers.provider.getNetwork()).chainId !== 31337n || manifest.chainId !== 31337) throw Error("Local Hardhat only");
  if (!process.env.DATABASE_URL) throw Error("Set DATABASE_URL to the isolated checkpoint database");
  let key = process.env.LOCAL_CHAIN_SIGNER_PRIVATE_KEY;
  if (!key) {
    const accounts = hre.config.networks.hardhat.accounts;
    if (!accounts.mnemonic) throw Error("Custom accounts: provide the authorized local key via environment");
    key = hre.ethers.HDNodeWallet.fromPhrase(accounts.mnemonic, undefined, "m/44'/60'/0'/0/1").privateKey;
  }
  const signer = new hre.ethers.Wallet(key);
  if (signer.address.toLowerCase() !== manifest.relayer.toLowerCase()) throw Error("Signer does not match manifest relayer");
  const root = path.resolve(__dirname, "../..");
  const python = process.env.CHECKPOINT_PYTHON || path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  const status = await new Promise((resolve, reject) => {
    const child = spawn(python, ["scripts/integrated_checkpoint.py"], {
      cwd: path.join(root, "backend"), stdio: "inherit", windowsHide: true,
      env: { ...process.env, LOCAL_CHAIN_SIGNER_PRIVATE_KEY: key, BLOCKCHAIN_RPC_URL: "http://127.0.0.1:8545",
             BLOCKCHAIN_CHAIN_ID: "31337", BLOCKCHAIN_DEPLOYMENT_FILE: path.join(root, "blockchain/deployments/localhost.json") }
    });
    child.on("error", reject);
    child.on("close", resolve);
  });
  process.exitCode = status ?? 1;
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
