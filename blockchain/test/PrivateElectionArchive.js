const { expect } = require('chai');
const { ethers } = require('hardhat');

describe('PrivateElectionArchive (anchor only)', function () {
  let contract, relayer, outsider;
  const b = text => ethers.keccak256(ethers.toUtf8Bytes(text));
  const election = b('synthetic-election'), config = b('configuration'), credentials = b('credentials');
  const ballot = b('ballot-id'), hash = b('ciphertext-and-proofs'), tag = b('credential-tag');

  beforeEach(async function () {
    const [admin, r, o] = await ethers.getSigners();
    relayer = r; outsider = o;
    contract = await (await ethers.getContractFactory('PrivateElectionArchive')).deploy(admin.address, r.address);
  });

  it('freezes commitments, enforces one tag, and seals an exact count', async function () {
    await contract.connect(relayer).configure(election, config, credentials);
    await expect(contract.connect(relayer).configure(election, b('changed'), credentials)).to.be.revertedWithCustomError(contract, 'InvalidState');
    await expect(contract.connect(relayer).anchorBallot(election, ballot, hash, tag)).to.be.revertedWithCustomError(contract, 'InvalidState');
    await contract.connect(relayer).open(election);
    await contract.connect(relayer).anchorBallot(election, ballot, hash, tag);
    await expect(contract.connect(relayer).anchorBallot(election, b('second'), hash, tag)).to.be.revertedWithCustomError(contract, 'DuplicateCredential');
    await expect(contract.connect(relayer).anchorBallot(election, ballot, hash, b('another'))).to.be.revertedWithCustomError(contract, 'DuplicateBallot');
    await expect(contract.connect(relayer).seal(election, b('archive'), 0)).to.be.revertedWithCustomError(contract, 'InvalidInput');
    await contract.connect(relayer).seal(election, b('archive'), 1);
    const state = await contract.getElection(election);
    expect(state.configurationHash).to.equal(config);
    expect(state.credentialsHash).to.equal(credentials);
    expect(state.archiveHash).to.equal(b('archive'));
    expect(state.count).to.equal(1);
    expect(await contract.ballotHashes(election, ballot)).to.equal(hash);
    expect(await contract.ballotCredentialTags(election, ballot)).to.equal(tag);
    await expect(contract.connect(relayer).anchorBallot(election, b('late'), hash, b('late-tag'))).to.be.revertedWithCustomError(contract, 'InvalidState');
    await expect(contract.connect(relayer).seal(election, b('other'), 1)).to.be.revertedWithCustomError(contract, 'InvalidState');
  });

  it('rejects unauthorized open, ballot and seal writes', async function () {
    await expect(contract.connect(outsider).configure(election, config, credentials)).to.be.reverted;
    await contract.connect(relayer).configure(election, config, credentials);
    await expect(contract.connect(outsider).open(election)).to.be.reverted;
    await contract.connect(relayer).open(election);
    await expect(contract.connect(outsider).anchorBallot(election, ballot, hash, tag)).to.be.reverted;
    await expect(contract.connect(outsider).seal(election, b('archive'), 0)).to.be.reverted;
  });

  it('rejects writes for another or unconfigured election', async function () {
    const other = b('wrong-election');
    await contract.connect(relayer).configure(election, config, credentials);
    await contract.connect(relayer).open(election);
    await expect(contract.connect(relayer).open(other)).to.be.revertedWithCustomError(contract, 'InvalidState');
    await expect(contract.connect(relayer).anchorBallot(other, ballot, hash, tag)).to.be.revertedWithCustomError(contract, 'InvalidState');
    await expect(contract.connect(relayer).seal(other, b('archive'), 0)).to.be.revertedWithCustomError(contract, 'InvalidState');
  });

  it('does not claim to stop a malicious authorized relayer inserting a new tag', async function () {
    await contract.connect(relayer).configure(election, config, credentials);
    await contract.connect(relayer).open(election);
    await contract.connect(relayer).anchorBallot(election, ballot, hash, b('not-proven-eligible'));
    expect((await contract.getElection(election)).count).to.equal(1);
  });
});
