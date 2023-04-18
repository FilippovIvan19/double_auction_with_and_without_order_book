import bisect
import random
import time
from otree.api import *


doc = """
Your app description
"""


class C(BaseConstants):
    NAME_IN_URL = 'double_auction'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1
    ITEMS_PER_PLAYER = 5
    PERIOD_DURATION = 150
    PERIOD_DURATION1 = 210
    # todo add borders of prices


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    start_timestamp = models.IntegerField()
    end_timestamp = models.IntegerField()


class Player(BasePlayer):
    break_even_points = models.StringField()
    num_items = models.IntegerField()
    round_payoff = models.IntegerField()
    is_buyer = models.BooleanField()
    current_offer = models.FloatField()


# PAGES
class InitPage(WaitPage):
    @staticmethod
    def after_all_players_arrive(group: Group):
        group.start_timestamp = int(time.time())
        if group.round_number == 1:
            group.end_timestamp = group.start_timestamp + C.PERIOD_DURATION1
        else:
            group.end_timestamp = group.start_timestamp + C.PERIOD_DURATION

        for p in group.get_players():
            p.is_buyer = (p.id_in_group + group.round_number) % 2 == 0
            p.num_items = 0 if p.is_buyer else C.ITEMS_PER_PLAYER
            p.current_offer = 0 if p.is_buyer else 200  # todo
            p.round_payoff = 0
            break_even_points = [random.uniform(1, 100) for _ in range(C.ITEMS_PER_PLAYER)]  #todo borders
            break_even_points.sort(reverse=p.is_buyer)
            break_even_points = [f'{price:.2f}' for price in break_even_points]
            p.break_even_points = ', '.join(break_even_points)


# todo
def find_match():
    pass


def insert_bid(bids, buyers, offer, player_id):
    try:
        index_for_deletion = buyers.index(player_id)
        del buyers[index_for_deletion]
        del bids[index_for_deletion]
    except ValueError:
        pass
    index_for_insertion = bisect.bisect_left(bids, offer)
    bids.insert(index_for_insertion, offer)
    buyers.insert(index_for_insertion, player_id)


def insert_ask(asks, sellers, offer, player_id):
    try:
        index_for_deletion = sellers.index(player_id)
        del sellers[index_for_deletion]
        del asks[index_for_deletion]
    except ValueError:
        pass
    index_for_insertion = bisect.bisect_right(asks, offer)
    asks.insert(index_for_insertion, offer)
    sellers.insert(index_for_insertion, player_id)


class GamePage(Page):
    bids = []  # buy offers,  highest in the end of list, last  element dealt first
    asks = []  # sell offers, highest in the end of list, first element dealt first
    buyers = []  # player_ids of offer owners
    sellers = []

    @staticmethod
    def js_vars(player: Player):
        return dict(is_buyer=player.is_buyer, buyer_num=C.ITEMS_PER_PLAYER)

    @staticmethod
    def get_timeout_seconds(player: Player):
        return player.group.end_timestamp - time.time()

    # todo
    # todo discard offer
    @staticmethod
    def live_method(player: Player, data):
        offer = float(data['offer'])
        player.current_offer = offer
        if player.is_buyer:
            insert_bid(GamePage.bids, GamePage.buyers, offer, player.id_in_group)
        else:
            insert_ask(GamePage.asks, GamePage.sellers, offer, player.id_in_group)

        players = player.group.get_players()
        return {
            p.id_in_group: dict(
                num_items=p.num_items,
                current_offer=p.current_offer,
                current_payoff=p.round_payoff,
                break_even_points=p.break_even_points,
                bids=GamePage.bids[::-1],
                asks=GamePage.asks,
            )
            for p in players
        }


class ResultsWaitPage(WaitPage):
    pass


class Results(Page):
    pass


page_sequence = [InitPage, GamePage, ResultsWaitPage, Results]
