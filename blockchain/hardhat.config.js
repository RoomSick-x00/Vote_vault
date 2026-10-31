require("@nomicfoundation/hardhat-ethers");
require("@nomicfoundation/hardhat-chai-matchers");
const { subtask } = require("hardhat/config");
const { TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD } = require("hardhat/builtin-tasks/task-names");
// Use the pinned npm compiler rather than a separate compiler download.
subtask(TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD).setAction(async ({ solcVersion }, _, runSuper) => {
  if (solcVersion === "0.8.24") return {
    compilerPath: require.resolve("solc/soljson.js"), isSolcJs: true,
    version: solcVersion, longVersion: require("solc").version()
  };
  return runSuper();
});
module.exports = {
  solidity: { version: "0.8.24", settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: "paris" } },
  networks: { hardhat: { chainId: 31337 }, localhost: { url: process.env.VV_LOCAL_RPC || "http://127.0.0.1:8545", chainId: 31337 } }
};
