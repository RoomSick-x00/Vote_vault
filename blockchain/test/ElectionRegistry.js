const { expect } = require("chai");
const { ethers } = require("hardhat");
const id = n => ethers.zeroPadValue(ethers.toBeHex(n), 32);
describe("ElectionRegistry", function () {
  let c, admin, relayer, stranger;
  const election = id(1), ballot = id(2), commitment = id(3), result = id(4);
  beforeEach(async function () {
    [admin, relayer, stranger] = await ethers.getSigners();
    c = await ethers.deployContract("ElectionRegistry", [admin.address, relayer.address]);
    c = c.connect(relayer);
  });
  const register = async () => c.registerElection(election, commitment);
  const open = async () => { await register(); await c.openElection(election); };
  it("records the normal lifecycle and exact commitment events", async function () {
    await expect(register()).to.emit(c,"ElectionRegistered").withArgs(election,commitment);
    await expect(c.openElection(election)).to.emit(c,"ElectionOpened").withArgs(election);
    await expect(c.publishBallot(election,ballot,commitment)).to.emit(c,"BallotPublished").withArgs(election,ballot,commitment);
    expect(await c.ballotCommitments(election,ballot)).to.equal(commitment);
    await expect(c.closeElection(election)).to.emit(c,"ElectionClosed").withArgs(election);
    await expect(c.publishResult(election,result)).to.emit(c,"ResultPublished").withArgs(election,result);
    expect(await c.getElection(election)).to.deep.equal([3n,commitment,result,1n]);
  });
  it("rejects every unauthorized write, including admin without relayer role", async function () {
    for (const signer of [admin,stranger]) {
      const x=c.connect(signer);
      for (const [method,args] of [["registerElection",[election,commitment]],["openElection",[election]],["closeElection",[election]],["publishBallot",[election,ballot,commitment]],["publishResult",[election,result]]]) {
        await expect(x[method](...args)).to.be.revertedWithCustomError(c,"AccessControlUnauthorizedAccount").withArgs(signer.address,await c.RELAYER_ROLE());
      }
    }
    await expect(c.grantRole(await c.RELAYER_ROLE(),stranger.address)).to.be.revertedWithCustomError(c,"AccessControlUnauthorizedAccount");
  });
  it("rejects duplicate ballot publication without incrementing count", async function () {
    await open(); await c.publishBallot(election,ballot,commitment);
    for (const value of [commitment,result]) await expect(c.publishBallot(election,ballot,value)).to.be.revertedWithCustomError(c,"BallotAlreadyPublished");
    expect((await c.getElection(election)).ballotCount).to.equal(1n);
    expect((await c.queryFilter(c.filters.BallotPublished(election,ballot))).length).to.equal(1);
  });
  it("rejects ballots before registration, before opening and after closure", async function () {
    await expect(c.publishBallot(election,ballot,commitment)).to.be.revertedWithCustomError(c,"InvalidState");
    await register();
    await expect(c.publishBallot(election,ballot,commitment)).to.be.revertedWithCustomError(c,"InvalidState");
    await c.openElection(election); await c.closeElection(election);
    await expect(c.publishBallot(election,ballot,commitment)).to.be.revertedWithCustomError(c,"InvalidState");
  });
  it("rejects re-registration, early close, repeated open/close and reopening", async function () {
    await expect(c.openElection(election)).to.be.revertedWithCustomError(c,"InvalidState");
    await register();
    await expect(register()).to.be.revertedWithCustomError(c,"InvalidState");
    await expect(c.closeElection(election)).to.be.revertedWithCustomError(c,"InvalidState");
    await c.openElection(election);
    await expect(c.openElection(election)).to.be.revertedWithCustomError(c,"InvalidState");
    await c.closeElection(election);
    await expect(c.closeElection(election)).to.be.revertedWithCustomError(c,"InvalidState");
    await expect(c.openElection(election)).to.be.revertedWithCustomError(c,"InvalidState");
  });
  it("rejects results before closure and a second result", async function () {
    await open();
    await expect(c.publishResult(election,result)).to.be.revertedWithCustomError(c,"InvalidState");
    await c.closeElection(election); await c.publishResult(election,result);
    await expect(c.publishResult(election,result)).to.be.revertedWithCustomError(c,"ResultAlreadyPublished");
  });
  it("rejects zero identifiers/commitments and zero constructor addresses", async function () {
    await expect(ethers.deployContract("ElectionRegistry",[ethers.ZeroAddress,relayer.address])).to.be.revertedWithCustomError(c,"ZeroValue");
    await expect(ethers.deployContract("ElectionRegistry",[admin.address,ethers.ZeroAddress])).to.be.revertedWithCustomError(c,"ZeroValue");
    await expect(c.registerElection(ethers.ZeroHash,commitment)).to.be.revertedWithCustomError(c,"ZeroValue");
    await expect(c.registerElection(election,ethers.ZeroHash)).to.be.revertedWithCustomError(c,"ZeroValue");
    await open();
    await expect(c.publishBallot(election,ethers.ZeroHash,commitment)).to.be.revertedWithCustomError(c,"ZeroValue");
    await expect(c.publishBallot(election,ballot,ethers.ZeroHash)).to.be.revertedWithCustomError(c,"ZeroValue");
    await c.closeElection(election);
    await expect(c.publishResult(election,ethers.ZeroHash)).to.be.revertedWithCustomError(c,"ZeroValue");
  });
  it("scopes ballot IDs to elections", async function () {
    await open(); await c.registerElection(id(9),commitment); await c.openElection(id(9));
    await c.publishBallot(election,ballot,commitment); await c.publishBallot(id(9),ballot,result);
    expect(await c.ballotCommitments(election,ballot)).to.equal(commitment);
    expect(await c.ballotCommitments(id(9),ballot)).to.equal(result);
  });
});
