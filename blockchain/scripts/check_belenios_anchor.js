// Read-only verifier for the synthetic Belenios archive anchor contract.
const fs = require("node:fs");
const path = require("node:path");
const { ethers } = require("ethers");
const hre = process.env.VV_USE_HARDHAT_PROVIDER === "1" ? require("hardhat") : null;

async function main() {
  const inputPath = process.env.VV_CHAIN_INPUT || process.argv[2];
  if (!inputPath) throw new Error("Provide the verifier input JSON path.");
  const input = JSON.parse(fs.readFileSync(inputPath, "utf8"));
  const artifactPath = path.join(__dirname, "..", "artifacts", "contracts", "PrivateElectionArchive.sol", "PrivateElectionArchive.json");
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
  const checks = [];
  const add = (id, status, reason) => checks.push({ id, status, reason });
  try {
    let provider;
    if (process.env.VV_USE_HARDHAT_PROVIDER === "1") {
      const configuredRpc = hre.network.config.url;
      if (configuredRpc !== input.rpc) {
        add("chain.reference", "FAIL", `Hardhat RPC ${configuredRpc} differs from pinned RPC ${input.rpc}.`);
        return emit();
      }
      provider = hre.ethers.provider;
    } else {
      provider = new ethers.JsonRpcProvider(input.rpc);
    }
    const actualChainId = Number(BigInt(await provider.send("eth_chainId", [])));
    if (actualChainId !== input.chain_id) {
      add("chain.reference", "FAIL", "Connected chain ID differs from the pinned chain ID.");
      return emit();
    }
    const address = ethers.getAddress(input.contract);
    const code = await provider.getCode(address);
    if (code === "0x" || ethers.keccak256(code).toLowerCase() !== input.code_hash.toLowerCase()) {
      add("chain.reference", "FAIL", "Contract is missing or runtime code differs from the pinned hash.");
      return emit();
    }
    const contract = new ethers.Contract(address, artifact.abi, provider);
    const state = await contract.getElection(input.election_id);
    if (Number(state.state) !== 3) {
      add("chain.sealed", "INCOMPLETE", "Election is not sealed on the pinned contract.");
      return emit();
    }
    if (state.archiveHash.toLowerCase() !== input.archive_hash.toLowerCase()) {
      add("chain.archive", "FAIL", "Exact public archive bytes do not match the sealed archive hash.");
      return emit();
    }
    add("chain.archive", "PASS", "Exact public archive bytes match the sealed chain commitment.");
    const configOk = state.configurationHash.toLowerCase() === input.configuration_hash.toLowerCase();
    add("chain.configuration", configOk ? "PASS" : "FAIL", configOk ? "Belenios election and trustee data match frozen chain configuration." : "Belenios election/trustee data differs from frozen chain configuration.");
    const credentialsOk = state.credentialsHash.toLowerCase() === input.credentials_hash.toLowerCase();
    add("chain.credentials", credentialsOk ? "PASS" : "FAIL", credentialsOk ? "Belenios credential set matches frozen chain commitment." : "Belenios credential set differs from frozen chain commitment.");
    const countOk = BigInt(state.count) === BigInt(input.ballots.length);
    add("chain.ballot_count", countOk ? "PASS" : "FAIL", countOk ? `All ${input.ballots.length} accepted archive ballots are accounted for.` : "Archive ballot count differs from the sealed chain count.");
    const outcomes = await Promise.all(input.ballots.map(async (ballot) => {
      const [hash, tag] = await Promise.all([
        contract.ballotHashes(input.election_id, ballot.ballot_id),
        contract.ballotCredentialTags(input.election_id, ballot.ballot_id),
      ]);
      return hash.toLowerCase() === ballot.ballot_hash.toLowerCase()
        && tag.toLowerCase() === ballot.credential_tag.toLowerCase();
    }));
    const allMatch = outcomes.length === Number(state.count) && outcomes.every(Boolean);
    add("chain.ballots", allMatch ? "PASS" : "FAIL", allMatch ? "Every raw ballot and credential tag matches its anchored chain record." : "At least one ballot or credential tag is missing or differs from the chain.");
  } catch (error) {
    add("chain.reference", "INCOMPLETE", `Pinned chain could not be checked: ${error.message}`);
  }
  emit();

  function emit() {
    console.log(JSON.stringify(checks));
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
