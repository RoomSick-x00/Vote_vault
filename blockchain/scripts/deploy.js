const { ethers, artifacts } = require("hardhat");
const fs = require("node:fs");
const path = require("node:path");
async function main() {
  const network = await ethers.provider.getNetwork();
  if (network.chainId !== 31337n) throw Error("Local deployment only");
  const [admin, relayer] = await ethers.getSigners();
  const registry = await ethers.deployContract("ElectionRegistry", [admin.address, relayer.address]);
  await registry.waitForDeployment();
  const receipt = await registry.deploymentTransaction().wait();
  const artifact = await artifacts.readArtifact("ElectionRegistry");
  const out = path.join(__dirname, "..", "deployments", "localhost");
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(path.join(out, "ElectionRegistry.abi.json"), JSON.stringify(artifact.abi, null, 2) + "\n");
  const manifest = { chainId: Number(network.chainId), address: await registry.getAddress(), admin: admin.address,
    relayer: relayer.address, transactionHash: receipt.hash, blockNumber: receipt.blockNumber,
    runtimeCodeHash: ethers.keccak256(await ethers.provider.getCode(await registry.getAddress())) };
  fs.writeFileSync(path.join(out, "deployment.json"), JSON.stringify(manifest, null, 2) + "\n");
  fs.writeFileSync(path.join(out, "..", "localhost.json"), JSON.stringify({ ...manifest, abi: artifact.abi }, null, 2) + "\n");
  console.log(JSON.stringify(manifest, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
