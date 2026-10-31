// Anchor one synthetic Belenios archive into the isolated test contract.
// Never submit student records or run this against a real election.
const fs = require("node:fs");
const { ethers, artifacts } = require("hardhat");

async function main() {
  const [admin, relayer] = await ethers.getSigners();
  const network = await ethers.provider.getNetwork();
  if (network.chainId !== 31337n) throw new Error("Refusing non-local chain");
  const manifestPath = process.env.VV_ANCHOR_MANIFEST;
  const outputPath = process.env.VV_ANCHOR_OUTPUT;
  if (!manifestPath || !outputPath) throw new Error("Set VV_ANCHOR_MANIFEST and VV_ANCHOR_OUTPUT to public synthetic files.");
  const m = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  if (m.version !== "VV_BELENIOS_ANCHOR_1") throw new Error("Unrecognized manifest version");
  const Factory = await ethers.getContractFactory("PrivateElectionArchive");
  const contract = await Factory.deploy(admin.address, relayer.address);
  await contract.waitForDeployment();
  const electionId = m.election_id;
  await (await contract.connect(relayer).configure(electionId, m.configuration_hash, m.credentials_hash)).wait();
  await (await contract.connect(relayer).open(electionId)).wait();
  for (const ballot of m.ballots) {
    await (await contract.connect(relayer).anchorBallot(electionId, ballot.ballot_id, ballot.ballot_hash, ballot.credential_tag)).wait();
  }
  await (await contract.connect(relayer).seal(electionId, m.archive_hash, m.ballot_count)).wait();
  const address = await contract.getAddress();
  const artifact = await artifacts.readArtifact("PrivateElectionArchive");
  const codeHash = ethers.keccak256(await ethers.provider.getCode(address));
  const output = {
    chain_id: Number(network.chainId),
    rpc: process.env.VV_LOCAL_RPC || "http://127.0.0.1:8545",
    contract: address,
    code_hash: codeHash,
    election_id: electionId,
    configuration_hash: m.configuration_hash,
    credentials_hash: m.credentials_hash,
    archive_hash: m.archive_hash,
    ballot_count: m.ballot_count,
    synthetic_only: true,
    contract_abi: artifact.abi,
  };
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2) + "\n", { flag: "wx" });
  console.log(JSON.stringify({ chain_id: output.chain_id, contract: address, code_hash: codeHash, election_id: electionId, ballot_count: m.ballot_count }, null, 2));
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
