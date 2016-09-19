# -*- coding: utf-8 -*-

import telebot
import constants
import logging
import sys
from player_path_generator import player_path_generator
import random
from statistics import median

# Заводим лог
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s', handlers=[logging.StreamHandler()])
logging.info("Starting things")

# Вводим константы
n_players = 48
n_players_in_team = 6
n_tours = 7
n_questions = 5

# Счетчик туров
current_tour = 0
# Флаг перерыва - можно вводить результаты
is_break = False

# chat_id ведущего игры (чтобы никто не хакнул систему случайно)
admin_id = constants.admin_id

# Создаем шаблоны словарей
chat_player = {}          # {chat_id: player_id}
player_chat = {}          # {player_id: (chat_id, first_name, last_name)}
player_scores = {}        # {player_id: [tour_1, tour_2, ...]}
team_scores = {}          # {team: [tour_1, tour_2, ...]}
team_scores_in_tour = {}  # {team: [player_1_score, player_2_score, ...]}
players_in_team = {}      # {team: [player_1, player_2, ...]}
teams_for_players = player_path_generator(n_players, n_players_in_team, n_tours)  # {player_id: [team_1, team_2, ...]}
vote_rating = {}          # {player_id: number_of_votes}
liked_players = {}        # {chat_id: [liked_player_1, liked_player_2]}


# Сохраняем таблицу маршрутных листов в csv
with open('teams_for_players.csv', 'w') as f:
    table = ''
    for player in teams_for_players:
        table += '%s,%s\n' % (player, ','.join(teams_for_players[player]))
    f.write(table)

# Запускаем бота
bot = telebot.TeleBot(constants.token)


def signal_term_handler(signal, frame):
    """
        Обработка сигнала о конце всему
    """
    logging.info('got SIGTERM/SIGINT')
    sys.exit(0)


def get_chat_id_from_string(s):
    return int(s[2:])


def get_tournament_table(player_scores):
    table = 'Турнирная таблица:\n'
    for player in player_scores:
        if player in player_chat:
            table += '%s %s\t%s=%s\n' % (player_chat[player][1], player_chat[player][2], '+'.join(str(v) for v in player_scores[player]) ,sum(player_scores[player]))
    return table

def get_vote_table(vote_rating):
    vote_table = 'Результаты голосования: \n'
    for player in vote_rating:
        if player in player_chat:
            vote_table += '%s %s - %s' % (player_chat[player][1], player_chat[player][2], vote_rating[player])
    return vote_table

def get_liked_players(liked_players, chat_id):
    likes = 'Понравившиеся игроки:\n'
    for player in liked_players[chat_id]:
        likes += '%s: %s %s\n' % (player, player_chat[player][1], player_chat[player][2])
    return likes


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id,
                     "Привет! \nСегодня мы будем играть в ЧГК по правилам Кубка дружбы. "
                     "Введите id, который ты получил при регистрации, в формате id[число] (например, id23).\n\n"
                     "Будьте внимательны! Возможности исправить id у вас не будет!")


# Получить chat_id, чтобы задать права администратора
@bot.message_handler(commands=['chatid'])
def get_chat_id(message):
    bot.send_message(message.chat.id, str(message.chat.id))


@bot.message_handler(regexp='^[Ii][Dd][0-9]+$')
def register_player_id(message):
    player_id = get_chat_id_from_string(message.text)
    # Если игрок ввел id больший, чем число игроков
    if player_id >= n_players:
        bot.send_message(message.chat.id, '%s некорректен, попробуйте еще раз' % message.text)
        return

    # Выдача маршрутного листа
    if message.chat.id not in chat_player:
        if player_id not in player_chat:
            bot.send_message(message.chat.id, '%s, вы зарегистрировали %s' % (message.from_user.first_name, message.text))
            if player_id in teams_for_players:
                bot.send_message(message.chat.id, 'Ваш маршрутный лист на эту игру:\n %s' % " ".join(teams_for_players[player_id]))
            chat_player[message.chat.id] = player_id
            player_chat[player_id] = (message.chat.id, message.from_user.first_name, message.from_user.last_name)
            logging.info(message.chat.id)
        else:
            bot.send_message(message.chat.id,
                             'Этот id уже зарегистрирован. Если вы уверены, что не ошиблись номером, обратитесь к ведущему игры.')
    # Возможность ввести id есть только один раз
    else:
        bot.send_message(message.chat.id,
                         'Вы уже зарегистрировали id. Если вы ошиблись при отправке, обратитесь к ведущему игры.')


# Начало игры
@bot.message_handler(commands=['startgame'])
def start_game(message):
    # Команды управления принимаются только от ведущего
    if message.chat.id != admin_id:
        bot.send_message(message.chat.id, "This isn't the backdoor you're looking for")
        return

    # Начало игры
    logging.info('Start tour %s' % current_tour)
    for chat_id in chat_player:
        bot.send_message(chat_id, 'Мы начинаем игру. Пожалуйста, садитесь за игровой стол %s' % teams_for_players[chat_player[chat_id]][0])

    # Очистка и формирование списков команд
    for team in players_in_team:
        players_in_team[team] = []
    for player in teams_for_players:
        next_team = teams_for_players[player][current_tour]
        if next_team not in players_in_team:
            players_in_team[next_team] = []
        players_in_team[next_team].append(player)

    print(players_in_team)

    # Отправим ведущему списки команд
    recaps = ''
    for team in sorted(players_in_team):
        recaps += '%s: %s\n' % (team, ' '.join(str(v) for v in players_in_team[team]))
    bot.send_message(admin_id, recaps)

    # Расскажем игрокам, с кем они играют
    for team in players_in_team:
        players_around_table = ''
        for player_id in players_in_team[team]:
            if player_id in player_chat:
                players_around_table += '%s: %s %s\n' % (player_id, player_chat[player_id][1], player_chat[player_id][2])
        for player_id in players_in_team[team]:
            if player_id in player_chat:
                bot.send_message(player_chat[player_id][0], 'Этот тур вы играете таким составом:\n %s' % players_around_table)


# Следующий тур
@bot.message_handler(commands=['nexttour'])
def next_tour(message):
    # Команды управления принимаются только от ведущего
    if message.chat.id != admin_id:
        bot.send_message(message.chat.id, "This isn't the backdoor you're looking for")
        return

    # Управление счетчиком
    global current_tour
    current_tour += 1

    # Заканчиваем перерыв
    global is_break
    is_break = False

    # Сохранение результатов команды в этом туре - медианы результатов, введенных игроками. Раздача результатов игрокам
    for team in team_scores_in_tour:
        if team_scores_in_tour[team]:
            score = int(median(team_scores_in_tour[team]))
        else:
            score = 0

        if team not in team_scores:
            team_scores[team] = []
        team_scores[team].append(score)

        for player in players_in_team[team]:
            if player not in player_scores:
                player_scores[player] = []
            player_scores[player].append(score)

        # Обнуляем поле для обсчета следующего тура
        team_scores_in_tour[team] = []


    # print(player_scores)
    # Рассылка турнирной таблицы
    t_table = get_tournament_table(player_scores)
    for chat_id in chat_player:
        bot.send_message(chat_id, t_table)

    # Отправим и ведущему турнирную таблицу
    bot.send_message(admin_id, t_table)

    # Если туры кончились, ничего дальше не делаем
    global n_tours
    if current_tour == n_tours:
        bot.send_message(message.chat.id, "Мы доиграли последний тур")
        return

    # Очистка старых и формирование новых списков команд
    for team in players_in_team:
        players_in_team[team] = []
    for player in teams_for_players:
        next_team = teams_for_players[player][current_tour]
        if next_team not in players_in_team:
            players_in_team[next_team] = []
        players_in_team[next_team].append(player)

    # Отправим ведущему списки команд на этот тур
    recaps = ''
    for team in sorted(players_in_team):
        recaps += '%s: %s\n' % (team, ' '.join(str(v) for v in players_in_team[team]))
    bot.send_message(admin_id, recaps)

    # Начало нового тура
    logging.info('Start tour %s' % current_tour)
    # Тут упало в прошлый раз с ошибкой изменения длины словаря во время итерации - так должно работать
    for chat_id in list(chat_player.keys()):
        bot.send_message(chat_id, 'Мы начинаем тур #%s. Пожалуйста, садитесь за игровой стол %s' % (current_tour+1, teams_for_players[chat_player[chat_id]][current_tour]))

    # Расскажем игрокам, с кем они играют
    for team in players_in_team:
        players_around_table = ''
        for player_id in players_in_team[team]:
            if player_id in player_chat:
                players_around_table += '%s: %s %s\n' % (player_id, player_chat[player_id][1], player_chat[player_id][2])
        for player_id in players_in_team[team]:
            if player_id in player_chat:
                bot.send_message(player_chat[player_id][0], 'Этот тур вы играете таким составом:\n %s' % players_around_table)


# Конец тура
@bot.message_handler(commands=['endtour'])
def end_tour(message):
    # Команды управления принимаются только от ведущего
    if message.chat.id != admin_id:
        bot.send_message(message.chat.id, "This isn't the backdoor you're looking for")
        return

    global is_break
    is_break = True

    for chat_id in chat_player:
        bot.send_message(chat_id, 'Мы доиграли тур #%s.\n'
                                  'Теперь вы можете отправить результат своей команды в этом туре. '
                                  'Пожалуйста, пришлите результат в виде числа (например: 3)' % (current_tour+1))


# Прием результатов
@bot.message_handler(regexp='^[0-9]+$')
def receive_result(message):

    if message.chat.id not in chat_player:
        bot.send_message(message.chat.id, 'Вы не зарегистрировали id и не можете отправлять результаты.')
        return

    if not is_break:
        bot.send_message(message.chat.id, 'Игра уже началась, вы сможете ввести результат и проголосовать за понравившихся игроков в перерыве.')
        return

    print(message.chat.id, 'send result', message.text)
    score = int(message.text)
    if score > n_questions:
        bot.send_message(message.chat.id, 'Так много очков вы набрать не могли. Попробуйте отправить правильное число.')
        return

    team = teams_for_players[chat_player[message.chat.id]][current_tour]
    if team not in team_scores_in_tour:
        team_scores_in_tour[team] = []
    team_scores_in_tour[team].append(score)

    bot.send_message(message.chat.id, 'Вы прислали результат вашей команды в этом туре. '
                                      'Если вы вдруг ошиблись, ничего страшного - коллеги вас поправят.\n\n'
                                      'Теперь вы можете отметить понравившегося игрока. Для этого отправьте vote[id игрока] (например: vote15)')


# Прием и подсчет голосов
@bot.message_handler(regexp='^[Vv]ote[0-9]+$')
def receive_vote(message):

    chat_id = message.chat.id
    voted_id = int(message.text[4:])

    if not is_break:
        bot.send_message(message.chat.id, 'Игра уже началась, вы сможете ввести результат и проголосовать за понравившихся игроков в перерыве.')
        return

    if voted_id not in player_chat:
        bot.send_message(chat_id, 'Вы не можете проголосовать за этот id, он не участвует в игре.')
        return

    if voted_id == chat_player[chat_id]:
        bot.send_message(chat_id, 'Вы не можете проголосовать за свой id.')
        return

    print(message.chat.id, 'send vote for', message.text)

    # Инициализируем голосование
    if chat_id not in liked_players:
        liked_players[chat_id] = []
    if voted_id not in vote_rating:
        vote_rating[voted_id] = 0

    if voted_id in liked_players[chat_id]:
        bot.send_message(chat_id, 'Вы уже отмечали этого игрока (id%s) как понравившегося.' % voted_id)
        return

    bot.send_message(chat_id, 'Вы отметили игрока %s %s (id%s) как понравившегося.' %
                     (player_chat[voted_id][1], player_chat[voted_id][2], voted_id))

    vote_rating[voted_id] += 1
    liked_players[chat_id].append(voted_id)


# Конец тура
@bot.message_handler(commands=['endgame'])
def end_game(message):
    # Команды управления принимаются только от ведущего
    if message.chat.id != admin_id:
        bot.send_message(message.chat.id, "This isn't the backdoor you're looking for")
        return

    global is_break
    is_break = False

    print(chat_player)
    t_table = get_tournament_table(player_scores)
    vote_table = get_vote_table(vote_rating)
    for chat_id in chat_player:
        liked = get_liked_players(liked_players, chat_id)
        bot.send_message(chat_id, 'Игра окончена! Вам будут отправлены результаты и список игроков, которых вы отметили')
        bot.send_message(chat_id, t_table)
        bot.send_message(chat_id, liked)
        bot.send_message(chat_id, vote_table)
        bot.send_message(chat_id, 'Спасибо за игру! Пожалуйста, дождитесь окончательных результатов')


# Надо как-то отвечать на все остальное
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    unknown_command_reaction = ['Не понимаю вас.', 'Зачем вы со мной так?', 'Я этого не умею.', 'Попробуйте что-нибудь другое.']
    bot.send_message(message.chat.id, random.choice(unknown_command_reaction))


if __name__ == '__main__':
    bot.polling(none_stop=True)

