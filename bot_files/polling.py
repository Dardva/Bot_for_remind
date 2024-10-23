import logging

import math
import requests
import sqlite3
import time

from exceptions import AlreadyExistsError
from random import choice
from telebot import TeleBot, types

from constants import ANIMAL_URLS, BOT_TOKEN, BOSSES
import logger_conf

logger = logging.getLogger(__name__)
bot = TeleBot(token=BOT_TOKEN)
conn = sqlite3.connect('bot.db', check_same_thread=False)
conn.execute('PRAGMA foreign_keys = ON')
cursor = conn.cursor()


def db_tables(slug: str, **args):

    if slug == 'users':
        cursor.execute(
            'SELECT id FROM users WHERE user_id_t = ?', (args['user_id_t'],)
        )
        row = cursor.fetchone()
        if not row:
            logger.debug('Добавляем нового пользователя в базу данных')
            cursor.execute(
                'INSERT INTO users (user_id_t, user_name, f_name, l_name)'
                'VALUES (?, ?, ?, ?)',
                (args['user_id_t'], args['user_name'],
                 args['f_name'], args['l_name'])
            )
        else:
            raise AlreadyExistsError

    if slug == 'groups':
        user_id_t = args['owner']['user_id_t']
        user_id = args['owner']['id']
        groups = take_groups(user_id_t, user_id=user_id)
        if args['name'] in [group['name'] for group in groups.values()]:
            raise AlreadyExistsError
        else:
            cursor.execute(
                'INSERT INTO groups (name, owner_id) VALUES (?, ?)',
                (args['name'], user_id))

            group_id = cursor.lastrowid

            cursor.execute(
                'INSERT INTO users_groups (user_id, group_id, add_note)'
                'VALUES (?, ?, 1)',
                (user_id, group_id))

    if slug == 'add_request':
        today = int(time.time())
        cursor.execute(
            'INSERT INTO requests (user_id, group_id, date) VALUES (?, ?)',
            (args['user_id'], args['group_id'], today)
        )

    if slug == 'add_member':
        cursor.execute(
            'INSERT INTO users_groups (user_id, group_id) VALUES (?, ?)',
            (args['user_id'], args['group_id'])
        )

    if slug == 'add_note':
        group_id = args.get('group_id')
        cursor.execute(
            'INSERT INTO notes (user_id, group_id, note) VALUES (?, ?, ?)',
            (args['user_id'], group_id, args['note'])
        )

    conn.commit()


def get_current_user(chat_id_t):
    try:
        cursor.execute(
            'SELECT id, user_id_t, user_name, f_name, l_name '
            'FROM users WHERE user_id_t = ?',
            [chat_id_t]
        )
    except Exception as error:
        logger.error('Ошибка при поиске пользователя', error)
        return
    row = cursor.fetchone()
    return {
        'id': row[0],
        'user_id_t': row[1],
        'user_name': row[2],
        'f_name': row[3],
        'l_name': row[4]
    }


def take_groups(chat, user_id=None):
    if user_id is None:
        user_id = get_current_user(chat.id)['id']
    try:
        cursor.execute(
            'SELECT groups.id, groups.name, groups.owner_id,'
            'users.user_name, users_groups.add_note '
            'FROM users_groups '
            'INNER JOIN groups ON users_groups.group_id = groups.id '
            'INNER JOIN users ON users_groups.user_id = users.id '
            'WHERE users_groups.user_id = ?', (user_id,))
    except Exception as error:
        logger.error('Ошибка при поиске групп', error)
        return None
    rows = cursor.fetchall()
    return {
        i: {
            'id': row[0],
            'name': row[1],
            'owner_id': row[2],
            'owner_user_name': row[3],
            'add_note': row[4]
        } for i, row in enumerate(rows, 1)}


def check_add_note(group_id, user_id_t):
    user_id = get_current_user(user_id_t)['id']
    cursor.execute(
        'SELECT add_note FROM users_groups WHERE group_id = ? AND user_id = ?',
        (group_id, user_id)
    )
    row = cursor.fetchone()
    if row and row[0] == 1:
        return True
    return False


def get_new_image():
    animal, url = choice(list(ANIMAL_URLS.items()))
    logger.debug(f'Отправляем запрос к API {animal}: {url}')
    try:
        response = requests.get(url).json()
        logger.debug(f'Получен ответ от API {animal}: {response}')

    except Exception as err:
        logger.error(f'При доступе к API возникла ошибка: {err}')
        new_animal, url = choice(list(ANIMAL_URLS.items()))
        while animal == new_animal:
            new_animal, url = choice(list(ANIMAL_URLS.items()))
        response = requests.get(url).json()
        logger.debug(f'Получен ответ от API {new_animal}: {response}')

    if isinstance(response, list):
        response = response[0]
    for value in response.values():
        if value.endswith(('.jpg', '.gif', '.png', '.jpeg')):
            return value


def boss_check(chat):
    if chat.id in BOSSES:
        return 'Хозяин'
    return f'{chat.first_name}'


def start_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_animal = types.KeyboardButton('/newanimal')  # check
    button_for_groups = types.KeyboardButton('/groups')  # check
    button_add_group = types.KeyboardButton('/newgroup')  # check
    button_for_me = types.KeyboardButton('/notes')  # in work
    button_help = types.KeyboardButton('/help')  # check
    button_requests = types.KeyboardButton('/group_requests')  # check
    keyboard.add(button_add_group, button_for_groups,
                 button_for_me, button_requests,
                 button_animal, button_help, row_width=3)
    return keyboard


@bot.message_handler(commands=['start'])
def wake_up(message):
    chat = message.chat
    chat_id = chat.id
    user_data = {'user_id_t': chat_id, 'user_name': chat.username,
                 'f_name': chat.first_name, 'l_name': chat.last_name}
    try:
        logger.debug('Добавляем пользователя')
        db_tables('users', **user_data)
    except AlreadyExistsError:
        pass
    except Exception as error:
        logger.error('Ошибка при добавлении пользователя', error)
    keyboard = start_keyboard()
    text = boss_check(chat) + ('! Спасибо, что вы включили меня!'
                               'Посмотрите, что я вам нашёл.')
    bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard,)
    bot.send_photo(chat.id, get_new_image())
    text_2 = ('Для получения списка команд нажмите /help')
    bot.send_message(chat_id=chat_id, text=text_2)


@bot.message_handler(commands=['help'])
def help(message):
    chat = message.chat
    bot.send_message(
        chat.id,
        '1. Для получения нового изображения нажмите /newanimal.\n\n'
        '2. Для получения списка групп,'
        'добавления групп или записок в группу нажмите /groups.\n\n'
        '3. Для создания группы /newgroup.\n\n'
        '4. Для просмотра своих записок'
        '5. или создания записки для себя нажмите /notes.\n\n'
        '6. Для получения подтверждения на добавление в группу'
        'нажмите /group_requests.')


@bot.message_handler(commands=['newanimal'])
def new_animal(message):
    chat = message.chat
    bot.send_photo(chat.id, get_new_image())


@bot.message_handler(commands=['groups'])  # check
def groups(message, page=1, previous_message=None):
    chat = message.chat
    groups_dict = take_groups(chat)
    text = 'Нет групп'
    buttons = types.InlineKeyboardMarkup()

    if groups_dict:
        pages_count = max(groups_dict.keys())
        text = (f'Группа: {groups_dict[page]["name"]}\n'
                f'Cоздал: {groups_dict[page]["owner_user_name"]}')
        group_id = groups_dict[page]['id']
        left = page-1 if page != 1 else pages_count
        right = page+1 if page != pages_count else 1
        left_button = types.InlineKeyboardButton(
            "←", callback_data=f'to {left} groups')
        page_button = types.InlineKeyboardButton(
            f"{str(page)}/{str(pages_count)}", callback_data='_')
        right_button = types.InlineKeyboardButton(
            "→", callback_data=f'to {right} groups')
        buttons.add(left_button, page_button, right_button)
        button_notes = types.InlineKeyboardButton(
            "Записки", callback_data=f'notes {group_id}')
        buttons.add(button_notes)
        if groups_dict[page]['owner_user_name'] == chat.username:
            button_rename = types.InlineKeyboardButton(
                'Переименовать', callback_data=f'rename {group_id}')
            button_delete = types.InlineKeyboardButton(
                'Удалить', callback_data=f'delete groups {group_id}')
            button_members = types.InlineKeyboardButton(
                'Участники', callback_data=f'members {group_id}')
            buttons.add(button_rename, button_delete,
                        button_members)
        else:
            button_delete_member = types.InlineKeyboardButton(
                'Покинуть группу',
                callback_data=f'delete_member {group_id} me'
            )
            buttons.add(button_delete_member)
    bot.send_photo(chat.id, photo=get_new_image(),
                   caption=text, reply_markup=buttons)
    try:
        bot.delete_message(message.chat.id, previous_message.id)
    except AttributeError:
        pass


@bot.message_handler(commands=['group_requests'])  # check
def requests_check(message, page=1, previous_message=None):
    chat = message.chat
    user = get_current_user(chat.id)
    groups_requests = {}

    try:
        cursor.execute(
            'SELECT groups.id, groups.name, groups.owner_id, '
            'users.user_name, users.user_id_t '
            'FROM requests '
            'INNER JOIN groups ON requests.group_id = groups.id '
            'INNER JOIN users ON groups.owner_id = users.id '
            'WHERE requests.user_id = ?',
            (user['id'],)
        )
        requests = cursor.fetchall()
    except Exception as error:
        logger.error(error)
    text = 'Нет запросов'
    buttons = types.InlineKeyboardMarkup()

    if requests:
        groups_requests = enumerate(requests, 1)
        pages_count = len(requests)
        text = f'Группа: {groups_requests[page][1]}, создал: {groups[page][3]}'
        left = page-1 if page != 1 else pages_count
        right = page+1 if page != pages_count else 1
        left_button = types.InlineKeyboardButton(
            "←", callback_data=f'to {left} requests')
        page_button = types.InlineKeyboardButton(
            f"{str(page)}/{str(pages_count)}", callback_data='_')
        right_button = types.InlineKeyboardButton(
            "→", callback_data=f'to {right} requests')
        buttons.add(left_button, page_button, right_button)

        add_button = types.InlineKeyboardButton(
            'Принять запрос',
            callback_data=(
                'add_request'
                f'{groups_requests[page][0]} {groups_requests[page][4]}')
        )
        buttons.add(add_button)

    bot.send_photo(chat.id, photo=get_new_image(),
                   caption=text, reply_markup=buttons)
    try:
        bot.delete_message(message.chat.id, previous_message.id)
    except AttributeError:
        pass


@bot.message_handler(commands=['notes'])
def notes(message, page=1, previous_message=None, group_id=None):
    chat = message.chat
    user = get_current_user(chat.id)
    group_id = (None, None)
    text = 'Нет записок'
    buttons = types.InlineKeyboardMarkup()
    try:
        if group_id:
            cursor.execute(
                'SELECT notes.note, notes.id, groups.name,'
                ' groups.id, users_groups.add_note, notes.user_id '
                'FROM users_groups '
                'INNER JOIN groups ON users_groups.group_id = groups.id '
                'INNER JOIN notes ON groups.id = notes.group_id '
                'WHERE (user_id = ? AND group_id = ?) OR notes.user_id = ?',
                (user['id'], group_id, user['id']))
        else:
            cursor.execute(
                'SELECT notes.note, notes.id, groups.name,'
                ' groups.id, users_groups.add_note, notes.user_id '
                'FROM users_groups '
                'INNER JOIN groups ON users_groups.group_id = groups.id '
                'INNER JOIN notes ON groups.id = notes.group_id '
                'WHERE user_id = ? OR notes.user_id = ?',
                (user['id'], user['id']))
    except Exception as error:
        logger.error(error)
    finally:
        rows = cursor.fetchall()

        if rows:
            notes_num = enumerate(rows)
            pages_count = len(rows)
            text = f'{notes_num[page][0]}'
            if notes_num[page][2]:
                text += f'\n Из Группы: {notes_num[page][2]}'
            left = page-1 if page != 1 else pages_count
            right = page+1 if page != pages_count else 1
            left_button = types.InlineKeyboardButton(
                "←", callback_data=f'to {left} notes')  # check
            page_button = types.InlineKeyboardButton(
                f"{str(page)}/{str(len(groups))}", callback_data='_')  # check
            right_button = types.InlineKeyboardButton(
                "→", callback_data=f'to {right} notes')  # check
            buttons.add(left_button, page_button, right_button)
            if notes_num[page][4] or notes_num[page][5] == user['id']:
                change_button = types.InlineKeyboardButton(
                    'Изменить заметку',
                    callback_data=f'change_note {notes_num[page][1]}')
                delete_button = types.InlineKeyboardButton(
                    'Удалить заметку',
                    callback_data=f'delete notes {notes_num[page][1]}')
                buttons.add(change_button, delete_button)
            new_note = types.InlineKeyboardButton(
                'Создать заметку', callback_data='add_note me')
            if notes_num[page][4]:
                button_add_group = types.InlineKeyboardButton(
                    'Создать заметку в группу',
                    callback_data=f'add_note {notes_num[page][3]}')
                buttons.add(new_note, button_add_group)
            else:
                buttons.add(new_note)
    bot.send_photo(chat.id, photo=get_new_image(),
                   caption=text, reply_markup=buttons)

    try:
        bot.delete_message(message.chat.id, previous_message.id)
    except AttributeError:
        pass


def members(message, page=1, previous_message=None, group_id=None):  # check
    chat = message.chat
    try:
        cursor.execute(
            'SELECT users_groups.group_id, groups.name,'
            ' users.user_name, users.user_id_t '
            'FROM users_groups '
            'INNER JOIN groups ON users_groups.group_id = groups.id '
            'INNER JOIN users ON users_groups.user_id = users.id '
            'WHERE users_groups.group_id = ?',
            (group_id,))
        rows = cursor.fetchall()
    except Exception as error:
        logger.error(error)
    if rows:
        buttons = types.InlineKeyboardMarkup()
        members = enumerate(rows, 1)
        pages_count = len(rows)
        text = 'Всего участников: ' + str(pages_count)
        end_list = pages_count if pages_count < page*10 else page*10
        current_list = list(members)[page*10-10:end_list]
        list_count = math.ceil(pages_count/10)
        left = page-1 if page != 1 else list_count
        right = page+1 if page != list_count else 1
        left_button = types.InlineKeyboardButton(
            "←", callback_data=f'to {left} members')
        page_button = types.InlineKeyboardButton(
            f"{str(page)}/{str(list_count)}", callback_data='_')
        right_button = types.InlineKeyboardButton(
            "→", callback_data=f'to {right} members')
        buttons.add(left_button, page_button, right_button)
        text += '\n'.join(f'{i}. {member[2]} - {member[1]}' for i,
                          member in current_list)
        if len(current_list) > 5:
            buttons.add(*[types.InlineKeyboardButton(
                f"{i}", callback_data=f'member {member[0]} {member[3]}'
            ) for i, member in current_list[:5]])
            buttons.add(*[types.InlineKeyboardButton(
                f"{i}", callback_data=f'member {member[0]} {member[3]}'
            ) for i, member in current_list[5:end_list]])
        else:
            buttons.add(*[types.InlineKeyboardButton(
                f"{i}", callback_data=f'member {member[0]} {member[3]}'
            ) for i, member in current_list[:end_list]])
        text += ('\n' + 'Выберете участника чтобы его удалить'
                 'или передать владение группой.')
        bot.send_photo(chat.id, photo=get_new_image(),
                       caption=text, reply_markup=buttons)
    try:
        bot.delete_message(message.chat.id, previous_message.id)
    except AttributeError:
        pass


@bot.message_handler(commands=['newgroup'])
def add_group(message):
    chat = message.chat
    bot.send_message(chat.id, 'Напишите название группы')
    bot.register_next_step_handler(message, add_group_name)


@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    data = c.data.split(' ')
    func_back_dict = {'groups': groups,
                      'requests': requests_check,
                      'notes': notes,
                      'members': members, }
    if data[0] == 'to':
        page = int(data[1])
        func_back_dict[data[2]](c.message, page=page,
                                previous_message=c.message)
    elif data[0] == 'add_request':
        add_member(c.message, group_id=data[1], owner_id_t=data[2])

    elif data[0] == 'notes':
        notes(c.message, previous_message=c.message, group_id=data[1])

    elif data[0] == 'rename':
        bot.send_message(c.message.chat.id,
                         'Напишите новое название группы или назад')
        bot.register_next_step_handler(c.message, rename_group, data[1])

    elif data[0] == 'delete':
        delete(c.message, data[2], data[1])

    elif data[0] == 'delete_member':
        delete_member(c.message, data[1], data[2])

    elif data[0] == 'members':
        members(c.message, previous_message=c.message, group_id=data[1])

    elif data[0] == 'member':
        member_info(c.message, data[1], data[2], previous_message=c.message)

    elif data[0] == 'make_owner':
        make_owner(c.message, data[1], data[2], data[3],
                   data[4], previous_message=c.message)

    elif data[0] == 'change_note':
        bot.send_message(c.message.chat.id, 'Напишите текст записки или назад')
        bot.register_next_step_handler(
            c.message, change_note, data[1], c.message)

    elif data[0] == 'add_note':
        bot.send_message(c.message.chat.id, 'Напишите текст записки')
        bot.register_next_step_handler(
            c.message, add_notes, data[1], c.message)


def add_group_name(message):  # check
    chat = message.chat
    group_name = message.text
    user = get_current_user(chat.id)
    logger.debug(user)
    group = {'name': group_name, 'owner': user}
    try:
        db_tables('groups', **group)
    except AlreadyExistsError:
        bot.send_message(chat.id, 'Такая группа уже существует.')
    except Exception as error:
        logger.error('Ошибка при добавлении группы', error)
    else:
        bot.send_message(chat.id, 'Группа добавлена!')


def change_note(message, note_id, previous_message):
    chat = message.chat
    new_name = message.text
    if new_name.lower() == 'назад':
        pass
    else:
        try:
            cursor.execute(
                'UPDATE notes SET text = ? WHERE id = ?',
                (new_name, note_id)
            )
        except Exception as error:
            logger.error('Ошибка при изменении записки', error)
            bot.send_message(chat.id, 'Ой, ошибка, попробуйте ещё раз.')
        else:
            bot.send_message(chat.id, 'Записка изменена!')
    notes(message, previous_message=previous_message)


def rename_group(message, group_id, previous_message):
    chat = message.chat
    new_name = message.text
    if new_name.lower() == 'назад':
        pass
    else:
        try:
            cursor.execute(
                'UPDATE groups SET name = ? WHERE id = ?',
                (new_name, group_id)
            )
        except Exception as error:
            logger.error('Ошибка при переименовании группы', error)
            bot.send_message(chat.id, 'Ой, ошибка, попробуйте ещё раз.')
        else:
            bot.send_message(chat.id, 'Группа переименована!')
    groups(message, previous_message=previous_message)


def delete(message, id, table):
    chat = message.chat
    try:
        cursor.execute(
            f'DELETE FROM {table} WHERE id = ?',
            (id,)
        )
    except Exception as error:
        logger.error('Ошибка при удалении группы', error)
        bot.send_message(chat.id, 'Ой, ошибка, попробуйте ещё раз.')
    else:
        conn.commit()
        bot.send_message(chat.id, 'Группа удалена!')
    groups(message, previous_message=message)


def delete_member(message, group_id, user_id_t):
    chat = message.chat
    if user_id_t == 'me':
        user_id_t = chat.id
    user_id = get_current_user(user_id_t)['id']
    cursor.execute(
        'SELECT name, owner_id FROM groups WHERE id = ?',
        (group_id,)
    )
    group = cursor.fetchone()
    if group[1] == user_id:
        bot.send_message(chat.id, 'Нельзя удалять владельца группы!')
        return
    try:
        cursor.execute(
            'DELETE FROM users_groups WHERE group_id = ? AND user_id = ?',
            (group_id, user_id)
        )
    except Exception as error:
        logger.error('Ошибка при удалении участника', error)
        bot.send_message(chat.id, 'Ой, ошибка, попробуйте ещё раз.')
    else:
        bot.send_message(chat.id, 'Участник удален!')
        bot.send_message(user_id_t, 'Вас удалили из группы ' + group[0])

    groups(message, previous_message=message)


def make_owner(message, group_id, user_id_t,
               group_name, owner_id_t,
               previous_message=None):
    chat = message.chat
    user = get_current_user(user_id_t)
    cursor.execute(
        'UPDATE groups SET owner_id = ? WHERE group_id = ?',
        (user['id'], group_id)
    )
    bot.send_message(chat.id, 'Вы стали владельцем группы ' + group_name)
    bot.send_message(owner_id_t, 'Вы перестали владельца группы ' + group_name)
    groups(message, previous_message=previous_message)


def member_info(message, previous_message, group_id, user_id_t):  # check
    chat = message.chat
    try:
        cursor.execute(
            'SELECT users_groups.group_id, groups.name,'
            ' users.user_name, users.user_id_t '
            'FROM users_groups '
            'INNER JOIN groups ON users_groups.group_id = groups.id '
            'INNER JOIN users ON users_groups.user_id = users.id '
            'WHERE users_groups.group_id = ?, users.user_id_t = ?',
            (group_id, user_id_t))
        rows = cursor.fetchall()[0]
    except Exception as error:
        logger.error('Ошибка при поиске участника', error)
        bot.send_message(message.chat.id, 'Ой, ошибка, попробуйте ещё раз.')
        return

    text = f'Группа: {rows[1]}\n Участник: {rows[2]}'
    buttons = types.InlineKeyboardMarkup()
    delete_button = types.InlineKeyboardButton(
        'Удалить', callback_data=f'delete_member {group_id} {user_id_t}'
    )
    make_owner = types.InlineKeyboardButton(
        'Сделать владельцем группы',
        callback_data=f'make_owner {group_id} {user_id_t} {rows[1]} {chat.id}'
    )
    buttons.add(delete_button, make_owner)
    bot.send_message(message.chat.id, text, reply_markup=buttons)
    try:
        bot.delete_message(message.chat.id, previous_message.id)
    except AttributeError:
        logger.error('Не удалось удалить предыдущее сообщение')


def add_request(message, group_id):
    chat = message.chat
    member = message.text
    user_slug = 'id_t'
    user_def = int(member)

    if member.startswith('@'):
        user_slug = 'name'
        user_def = member[1:]
    try:
        cursor.execute(
            ('SELECT id, user_id_t, user_name'
             f'FROM users WHERE user_{user_slug} = ?'),
            (user_def,)
        )
    except Exception as error:
        logger.error('Ошибка при  поиске участника', error)
        bot.send_message(chat.id, 'Ой, такого пользователя нет.')
        return

    user = cursor.fetchone()

    try:
        cursor.execute(
            'SELECT name FROM groups WHERE id = ?',
            (group_id,)
        )
    except Exception as error:
        logger.error('Ошибка при поиске группы', error)
        bot.send_message(chat.id, 'Ой, ошибка, попробуйте ещё раз.')
        return
    add_request = {'group_id': group_id, 'user_id': user[0]}
    db_tables('add_request', **add_request)
    group_name = cursor.fetchone()[0]
    bot.send_message(chat.id, 'Участнику отправлено приглашение!')
    groups(message)
    bot.send_message(
        user[1],
        f'@{chat.username}, Вас добавил в группу {group_name}!'
        'Перейдите в /home, чтобы присоединиться .')


def add_member(message, groups_id, owner_id_t):
    chat = message.chat
    user = get_current_user(chat.id)
    add_member = {'group_id': groups_id, 'user_id': user['id']}
    db_tables('add_member', **add_member)
    bot.send_message(chat.id, 'Вы добавлены в группу!')
    bot.send_message(owner_id_t, f'@{chat.username} приняЛ приглашение!')


def add_notes(message, group_id):
    chat = message.chat
    user = get_current_user(chat.id)
    add_note = {'user_id': user['id'], 'text': message.text}
    if isinstance(group_id, int):
        add_note['group_id'] = group_id

    db_tables('add_note', **add_note)
    bot.send_message(chat.id, 'Записка добавлена!')


def chat_polling():

    now = int(time.time())
    if now % 86400 in [0, 43200]:
        logger.debug('Удаляем старые запросы')
        cursor.execute(
            'DELETE FROM requests WHERE date < ?',
            (now - 86400,)
        )

    try:
        bot.polling()
    except Exception as error:
        logger.error(error)


if __name__ == '__main__':
    logger.info('Бот запущен.')
    chat_polling()
