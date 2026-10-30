// Local-only harness: fund a fresh ephemeral relayer and pass its key only via env.
// No private key is written to disk or printed.
const { ethers } = require("hardhat");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
async function main() {
  if ((await ethers.provider.getNetwork()).chainId !== 31337n) throw Error("Local only");
  const [admin] = await ethers.getSigners();
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname,"../deployments/localhost/deployment.json")));
  const registry = await ethers.getContractAt("ElectionRegistry", manifest.address, admin);
  const wallet = ethers.Wallet.createRandom();
  await (await admin.sendTransaction({ to: wallet.address, value: ethers.parseEther("1") })).wait();
  await (await registry.grantRole(await registry.RELAYER_ROLE(), wallet.address)).wait();
  let result;
  try {
    const root = path.resolve(__dirname,"../..");
    const python = process.env.CHECKPOINT_PYTHON || path.join(root,".venv",process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
    result = await new Promise((resolve, reject) => {
      const child = spawn(python,["-m","pytest","-q"], { cwd: path.join(root,"backend"), stdio: "inherit",
      env: { ...process.env, BLOCKCHAIN_RPC_URL: "http://127.0.0.1:8545", BLOCKCHAIN_CHAIN_ID: "31337",
             BALLOT_REGISTRY_CONTRACT_ADDRESS: manifest.address, LOCAL_CHAIN_SIGNER_PRIVATE_KEY: wallet.privateKey } });
      child.on("error", reject);
      child.on("close", status => resolve({ status }));
    });
  } finally {
    await (await registry.revokeRole(await registry.RELAYER_ROLE(),wallet.address)).wait();
  }
  process.exitCode = result.status ?? 1;
}
main().catch(error => { console.error(error.message); process.exitCode=1; });
