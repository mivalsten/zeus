"""
homomorphic workflow and algorithms for Helios

Ben Adida
2008-08-30
reworked 2011-01-09
"""


from helios.crypto import algs, utils
from . import WorkflowObject

TYPE = 'homomorphic'


class EncryptedAnswer(WorkflowObject):
    """
    An encrypted answer to a single election question
    """

    def __init__(self, choices=None, individual_proofs=None, overall_proof=None, randomness=None, answer=None):
        self.choices = choices
        self.individual_proofs = individual_proofs
        self.overall_proof = overall_proof
        self.randomness = randomness
        self.answer = answer

    @classmethod
    def generate_plaintexts(cls, pk, min=0, max=1):
        plaintexts = []
        running_product = 1

        # run the product up to the min
        for i in range(max+1):
            # if we're in the range, add it to the array
            if i >= min:
                plaintexts.append(algs.EGPlaintext(running_product, pk))

            # next value in running product
            running_product = (running_product * pk.g) % pk.p

        return plaintexts

    def verify_plaintexts_and_randomness(self, pk):
        """
        this applies only if the explicit answers and randomness factors are given
        we do not verify the proofs here, that is the verify() method
        """
        if not hasattr(self, 'answer'):
            return False

        for choice_num in range(len(self.choices)):
            choice = self.choices[choice_num]
            choice.pk = pk

            # redo the encryption
            # WORK HERE (paste from below encryption)

        return False

    def verify(self, pk, min=0, max=1):
        possible_plaintexts = self.generate_plaintexts(pk)
        homomorphic_sum = 0

        for choice_num in range(len(self.choices)):
            choice = self.choices[choice_num]
            choice.pk = pk
            individual_proof = self.individual_proofs[choice_num]

            # verify the proof on the encryption of that choice
            if not choice.verify_disjunctive_encryption_proof(possible_plaintexts, individual_proof, algs.EG_disjunctive_challenge_generator):
                return False

            # compute homomorphic sum if needed
            if max is not None:
                homomorphic_sum = choice * homomorphic_sum

        if max is not None:
            # determine possible plaintexts for the sum
            sum_possible_plaintexts = self.generate_plaintexts(pk, min=min, max=max)

            # verify the sum
            return homomorphic_sum.verify_disjunctive_encryption_proof(sum_possible_plaintexts, self.overall_proof, algs.EG_disjunctive_challenge_generator)
        else:
            # approval voting, no need for overall proof verification
            return True

# WORK HERE


class EncryptedVote(WorkflowObject):
    """
    An encrypted ballot
    """

    def __init__(self):
        self.encrypted_answers = None

    @property
    def datatype(self):
        # FIXME
        return "legacy/EncryptedVote"

    def _answers_get(self):
        return self.encrypted_answers

    def _answers_set(self, value):
        self.encrypted_answers = value

    answers = property(_answers_get, _answers_set)

    def verify(self, election):
        # right number of answers
        if len(self.encrypted_answers) != len(election.questions):
            return False

        # check hash
        if self.election_hash != election.hash:
            # print "%s / %s " % (self.election_hash, election.hash)
            return False

        # check ID
        if self.election_uuid != election.uuid:
            return False

        # check proofs on all of answers
        for question_num in range(len(election.questions)):
            ea = self.encrypted_answers[question_num]

            question = election.questions[question_num]
            min_answers = 0
            if 'min' in question:
                min_answers = question['min']

            if not ea.verify(election.public_key, min=min_answers, max=question['max']):
                return False

        return True


class DLogTable(object):
    """
    Keeping track of discrete logs
    """

    def __init__(self, base, modulus):
        self.dlogs = {}
        self.dlogs[1] = 0
        self.last_dlog_result = 1
        self.counter = 0

        self.base = base
        self.modulus = modulus

    def increment(self):
        self.counter += 1

        # new value
        new_value = (self.last_dlog_result * self.base) % self.modulus

        # record the discrete log
        self.dlogs[new_value] = self.counter

        # record the last value
        self.last_dlog_result = new_value

    def precompute(self, up_to):
        while self.counter < up_to:
            self.increment()

    def lookup(self, value):
        return self.dlogs.get(value, None)


class Tally(WorkflowObject):
    """
    A running homomorphic tally
    """

    @property
    def datatype(self):
        return "legacy/Tally"

    def __init__(self, *args, **kwargs):
        super(Tally, self).__init__()

        election = kwargs.get('election', None)
        self.tally = None
        self.num_tallied = 0

        if election:
            self.init_election(election)
            self.tally = [[0 for a in q['answers']] for q in self.questions]
        else:
            self.questions = None
            self.public_key = None
            self.tally = None

    def init_election(self, election):
        """
        given the election, initialize some params
        """
        self.election = election
        self.questions = election.questions
        self.public_key = election.public_key

    def add_vote_batch(self, encrypted_votes, verify_p=True):
        """
        Add a batch of votes. Eventually, this will be optimized to do an aggregate proof verification
        rather than a whole proof verif for each vote.
        """
        for vote in encrypted_votes:
            self.add_vote(vote, verify_p)

    def add_vote(self, encrypted_vote, verify_p=True):
        # do we verify?
        if verify_p:
            if not encrypted_vote.verify(self.election):
                raise Exception('Bad Vote')

        # for each question
        for question_num in range(len(self.questions)):
            question = self.questions[question_num]
            answers = question['answers']

            # for each possible answer to each question
            for answer_num in range(len(answers)):
                # do the homomorphic addition into the tally
                enc_vote_choice = encrypted_vote.encrypted_answers[question_num].choices[answer_num]
                enc_vote_choice.pk = self.public_key
                self.tally[question_num][answer_num] = encrypted_vote.encrypted_answers[question_num].choices[answer_num] * self.tally[question_num][answer_num]

        self.num_tallied += 1

    def decryption_factors_and_proofs(self, sk):
        """
        returns an array of decryption factors and a corresponding array of decryption proofs.
        makes the decryption factors into strings, for general Helios / JS compatibility.
        """
        # for all choices of all questions (double list comprehension)
        decryption_factors = []
        decryption_proof = []

        for question_num, question in enumerate(self.questions):
            answers = question['answers']
            question_factors = []
            question_proof = []

            for answer_num, answer in enumerate(answers):
                # do decryption and proof of it
                dec_factor, proof = sk.decryption_factor_and_proof(self.tally[question_num][answer_num])

                # look up appropriate discrete log
                # this is the string conversion
                question_factors.append(dec_factor)
                question_proof.append(proof)

            decryption_factors.append(question_factors)
            decryption_proof.append(question_proof)

        return decryption_factors, decryption_proof

    def decrypt_and_prove(self, sk, discrete_logs=None):
        """
        returns an array of tallies and a corresponding array of decryption proofs.
        """

        # who's keeping track of discrete logs?
        if not discrete_logs:
            discrete_logs = self.discrete_logs

        # for all choices of all questions (double list comprehension)
        decrypted_tally = []
        decryption_proof = []

        for question_num in range(len(self.questions)):
            question = self.questions[question_num]
            answers = question['answers']
            question_tally = []
            question_proof = []

            for answer_num in range(len(answers)):
                # do decryption and proof of it
                plaintext, proof = sk.prove_decryption(self.tally[question_num][answer_num])

                # look up appropriate discrete log
                question_tally.append(discrete_logs[plaintext])
                question_proof.append(proof)

            decrypted_tally.append(question_tally)
            decryption_proof.append(question_proof)

        return decrypted_tally, decryption_proof

    def verify_decryption_proofs(self, decryption_factors, decryption_proofs, public_key, challenge_generator):
        """
        decryption_factors is a list of lists of dec factors
        decryption_proofs are the corresponding proofs
        public_key is, of course, the public key of the trustee
        """

        # go through each one
        for q_num, q in enumerate(self.tally):
            for a_num, answer_tally in enumerate(q):
                # parse the proof
                #proof = algs.EGZKProof.fromJSONDict(decryption_proofs[q_num][a_num])
                proof = decryption_proofs[q_num][a_num]

                # check that g, alpha, y, dec_factor is a DH tuple
                if not proof.verify(public_key.g, answer_tally.alpha, public_key.y, int(decryption_factors[q_num][a_num]), public_key.p, public_key.q, challenge_generator):
                    return False

        return True

    def decrypt_from_factors(self, decryption_factors, public_key):
        """
        decrypt a tally given decryption factors

        The decryption factors are a list of decryption factor sets, for each trustee.
        Each decryption factor set is a list of lists of decryption factors (questions/answers).
        """

        # pre-compute a dlog table
        dlog_table = DLogTable(base=public_key.g, modulus=public_key.p)
        dlog_table.precompute(self.num_tallied)

        result = []

        # go through each one
        for q_num, q in enumerate(self.tally):
            q_result = []

            for a_num, a in enumerate(q):
                # coalesce the decryption factors into one list
                dec_factor_list = [df[q_num][a_num] for df in decryption_factors]
                raw_value = self.tally[q_num][a_num].decrypt(dec_factor_list, public_key)

                q_result.append(dlog_table.lookup(raw_value))

            result.append(q_result)

        return result

    def _process_value_in(self, field_name, field_value):
        if field_name == 'tally':
            return [[algs.EGCiphertext.fromJSONDict(a) for a in q] for q in field_value]

    def _process_value_out(self, field_name, field_value):
        if field_name == 'tally':
            return [[a.toJSONDict() for a in q] for q in field_value]


"""
Workflow api methods
"""


def tallied(election):
    return bool(election.encrypted_tally)


def compute_tally(election):
    tally = election.init_tally()
    for voter in election.voter_set.all():
        if voter.vote:
            tally.add_vote(voter.vote, verify_p=False)

    election.encrypted_tally = tally
    election.save()


def tally_hash(election):
    if not election.encrypted_tally:
        return None

    return utils.hash_b64(election.encrypted_tally.toJSON())


def ready_for_decription(election):
    return election.encrypted_tally is not None


def decrypt_tally(election, decryption_factors):
    return election.encrypted_tally.decrypt_from_factors(decryption_factors,
            election.public_key)


def get_decryption_factors_and_proof(election, key):
    tally = election.encrypted_tally
    tally.init_election(election)
    return tally.decryption_factors_and_proofs(key)


def verify_encryption_proof(election, trustee):
    return election.encrypted_tally.verify_decryption_proofs(
            trustee.decryption_factors,
            trustee.decryption_proofs,
            trustee.public_key,
            algs.EG_fiatshamir_challenge_generator)
