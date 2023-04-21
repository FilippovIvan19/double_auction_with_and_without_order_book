import bisect
import random
import time
from otree.api import *
from otree.models import Participant

doc = """
Your app description
"""


class C(BaseConstants):
    NAME_IN_URL = 'double_auction'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 4  # todo set to 24 in final version
    ITEMS_PER_PLAYER = 5
    DISCARD_OFFER_VAL = -1
    PERIOD_DURATION = 150
    PERIOD_DURATION1 = 210

    HALF1_BUYERS_PRICE_BORDERS1 = (25, 60)
    HALF1_SELLERS_PRICE_BORDERS1 = (0, 35)  # equilibrium = 30
    HALF1_BUYERS_PRICE_BORDERS2 = (30, 60)
    HALF1_SELLERS_PRICE_BORDERS2 = (10, 40)  # equilibrium = 35
    HALF2_BUYERS_PRICE_BORDERS1 = (20, 50)
    HALF2_SELLERS_PRICE_BORDERS1 = (0, 30)  # equilibrium = 25
    HALF2_BUYERS_PRICE_BORDERS2 = (25, 60)
    HALF2_SELLERS_PRICE_BORDERS2 = (0, 35)  # equilibrium = 30

    BORDERS = (HALF1_BUYERS_PRICE_BORDERS1, HALF1_SELLERS_PRICE_BORDERS1,
               HALF1_BUYERS_PRICE_BORDERS2, HALF1_SELLERS_PRICE_BORDERS2,
               HALF2_BUYERS_PRICE_BORDERS1, HALF2_SELLERS_PRICE_BORDERS1,
               HALF2_BUYERS_PRICE_BORDERS2, HALF2_SELLERS_PRICE_BORDERS2)


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    start_timestamp = models.IntegerField()
    end_timestamp = models.IntegerField()


class Player(BasePlayer):
    break_even_points = models.StringField()
    num_items = models.IntegerField()
    round_payoff = models.FloatField()
    is_buyer = models.BooleanField()
    current_offer = models.FloatField()
    full_name = models.StringField()


def str_to_float_arr(s: str):
    return list(map(float, s.split(', ')))


def float_arr_to_str(arr: list[float]):
    return ', '.join([f'{el:.2f}' for el in arr])


def get_break_even_points(is_buyer, round_number):
    borders = C.BORDERS
    if is_buyer:
        borders = borders[0::2]
    else:
        borders = borders[1::2]
    quarter = (round_number - 1) // (C.NUM_ROUNDS // 4)
    return [random.uniform(*borders[quarter]) for _ in range(C.ITEMS_PER_PLAYER)]


# PAGES
class InitPage(WaitPage):
    @staticmethod
    def after_all_players_arrive(group: Group):
        GamePage.bids, GamePage.asks, GamePage.buyers, GamePage.sellers = [], [], [], []
        GamePage.last_deal = C.DISCARD_OFFER_VAL

        group.start_timestamp = int(time.time())
        if group.round_number == 1:
            group.end_timestamp = group.start_timestamp + C.PERIOD_DURATION1
            for p in group.get_players():
                p.participant.full_name = p.full_name
        else:
            group.end_timestamp = group.start_timestamp + C.PERIOD_DURATION

        for p in group.get_players():
            p.is_buyer = (p.id_in_group + group.round_number) % 2 == 0
            p.num_items = 0 if p.is_buyer else C.ITEMS_PER_PLAYER
            p.current_offer = C.DISCARD_OFFER_VAL
            p.round_payoff = 0
            break_even_points = get_break_even_points(p.is_buyer, group.round_number)
            break_even_points.sort(reverse=p.is_buyer)
            p.break_even_points = float_arr_to_str(break_even_points)


def find_match(bids: list[float], asks: list[float],
               buyers: list[int], sellers: list[int]):
    if len(bids) > 0 and len(asks) > 0 and bids[-1] >= asks[0]:
        price = (bids.pop(-1) + asks.pop(0)) / 2.
        buyer, seller = buyers.pop(-1), sellers.pop(0)
        return price, buyer, seller
    else:
        return None


def insert_bid(bids: list[float], buyers: list[int], offer: float, player_id: int):
    try:
        index_for_deletion = buyers.index(player_id)
        del buyers[index_for_deletion]
        del bids[index_for_deletion]
    except ValueError:
        pass
    if offer != C.DISCARD_OFFER_VAL:
        index_for_insertion = bisect.bisect_left(bids, offer)
        bids.insert(index_for_insertion, offer)
        buyers.insert(index_for_insertion, player_id)


def insert_ask(asks: list[float], sellers: list[int], offer: float, player_id: int):
    try:
        index_for_deletion = sellers.index(player_id)
        del sellers[index_for_deletion]
        del asks[index_for_deletion]
    except ValueError:
        pass
    if offer != C.DISCARD_OFFER_VAL:
        index_for_insertion = bisect.bisect_right(asks, offer)
        asks.insert(index_for_insertion, offer)
        sellers.insert(index_for_insertion, player_id)


class GamePage(Page):
    bids = []  # buy offers,  highest in the end of list, last  element dealt first
    asks = []  # sell offers, highest in the end of list, first element dealt first
    buyers = []  # player_ids of offer owners
    sellers = []
    last_deal = C.DISCARD_OFFER_VAL

    @staticmethod
    def js_vars(player: Player):
        return dict(is_buyer=player.is_buyer,
                    buyer_num=C.ITEMS_PER_PLAYER,
                    discard_offer_val=C.DISCARD_OFFER_VAL)

    @staticmethod
    def get_timeout_seconds(player: Player):
        return player.group.end_timestamp - time.time()

    @staticmethod
    def live_method(player: Player, data):
        offer = float(data['offer'])
        player.current_offer = offer
        if player.is_buyer:
            insert_bid(GamePage.bids, GamePage.buyers, offer, player.id_in_group)
        else:
            insert_ask(GamePage.asks, GamePage.sellers, offer, player.id_in_group)

        if offer != C.DISCARD_OFFER_VAL:
            match = find_match(GamePage.bids, GamePage.asks,
                               GamePage.buyers, GamePage.sellers)
            if match:
                price, buyer_id, seller_id = match
                GamePage.last_deal = price
                buyer: Player = player.group.get_player_by_id(buyer_id)
                seller: Player = player.group.get_player_by_id(seller_id)

                buyer_break_even_points = str_to_float_arr(buyer.break_even_points)
                buyer.round_payoff += buyer_break_even_points.pop(0) - price
                buyer.break_even_points = float_arr_to_str(buyer_break_even_points)
                buyer.num_items += 1
                buyer.current_offer = C.DISCARD_OFFER_VAL

                seller_break_even_points = str_to_float_arr(seller.break_even_points)
                seller.round_payoff += price - seller_break_even_points.pop(0)
                seller.break_even_points = float_arr_to_str(seller_break_even_points)
                seller.num_items -= 1
                seller.current_offer = C.DISCARD_OFFER_VAL

        players = player.group.get_players()
        return {
            p.id_in_group: dict(
                num_items=p.num_items,
                current_offer=p.current_offer,
                current_payoff=f'{p.round_payoff:.2f}',
                break_even_points=p.break_even_points,
                bids=GamePage.bids[::-1],
                asks=GamePage.asks,
                last_deal=f'{GamePage.last_deal:.2f}',
            )
            for p in players
        }


class Registration(Page):
    form_model = 'player'
    form_fields = ['full_name']

    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1


class Instructions(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1


class ResultsWaitPage(WaitPage):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def after_all_players_arrive(group: Group):
        for p in group.get_players():
            # a: Participant = p.participant
            # a.id_in_session
            p.participant.result_payoff = sum(pr.round_payoff for pr in p.in_all_rounds())


def get_participant_info(p: Participant):
    return f'<tr><td>{p.id_in_session}</td>' \
           f'<td>{p.full_name}</td>' \
           f'<td>{p.result_payoff:.2f}</td></tr>'


class Results(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def js_vars(player: Player):
        return dict(participants=''.join([get_participant_info(p.participant)
                                          for p in player.group.get_players()])
                    )


page_sequence = [Registration, Instructions, InitPage, GamePage, ResultsWaitPage, Results]
# todo add custom export
# todo show order book only for first half
