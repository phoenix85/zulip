# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from zerver.lib.alert_words import (
    add_user_alert_words,
    alert_words_in_realm,
    remove_user_alert_words,
    user_alert_words,
)

from zerver.lib.test_helpers import (
    get_user_profile_by_email,
    most_recent_message,
    most_recent_usermessage,
)

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.models import (
    Recipient,
    UserProfile,
)

from typing import Text

import ujson

class AlertWordTests(ZulipTestCase):
    interesting_alert_word_list = ['alert', 'multi-word word', u'☃']

    def test_internal_endpoint(self):
        # type: () -> None
        email = "cordelia@zulip.com"
        self.login(email)

        params = {
            'alert_words': ujson.dumps(['milk', 'cookies'])
        }
        result = self.client_post('/json/users/me/alert_words', params)
        self.assert_json_success(result)
        user = get_user_profile_by_email(email)
        words = user_alert_words(user)
        self.assertEqual(words, ['milk', 'cookies'])

    def test_default_no_words(self):
        # type: () -> None
        """
        Users start out with no alert words.
        """
        user = self.example_user('cordelia')
        words = user_alert_words(user)
        self.assertEqual(words, [])

    def test_add_word(self):
        # type: () -> None
        """
        add_user_alert_words can add multiple alert words at once.
        """
        user = self.example_user('cordelia')

        # Add several words, including multi-word and non-ascii words.
        add_user_alert_words(user, self.interesting_alert_word_list)

        words = user_alert_words(user)
        self.assertEqual(words, self.interesting_alert_word_list)

    def test_remove_word(self):
        # type: () -> None
        """
        Removing alert words works via remove_user_alert_words, even
        for multi-word and non-ascii words.
        """
        user = self.example_user('cordelia')

        add_user_alert_words(user, self.interesting_alert_word_list)

        theoretical_remaining_alerts = self.interesting_alert_word_list[:]

        for alert_word in self.interesting_alert_word_list:
            remove_user_alert_words(user, alert_word)
            theoretical_remaining_alerts.remove(alert_word)
            actual_remaining_alerts = user_alert_words(user)
            self.assertEqual(actual_remaining_alerts,
                             theoretical_remaining_alerts)

    def test_realm_words(self):
        # type: () -> None
        """
        We can gather alert words for an entire realm via
        alert_words_in_realm. Alerts added for one user do not impact other
        users.
        """
        user1 = self.example_user('cordelia')

        add_user_alert_words(user1, self.interesting_alert_word_list)

        user2 = self.example_user('othello')
        add_user_alert_words(user2, ['another'])

        realm_words = alert_words_in_realm(user2.realm)
        self.assertEqual(len(realm_words), 2)
        self.assertEqual(list(realm_words.keys()), [user1.id, user2.id])
        self.assertEqual(realm_words[user1.id],
                         self.interesting_alert_word_list)
        self.assertEqual(realm_words[user2.id], ['another'])

    def test_json_list_default(self):
        # type: () -> None
        self.login("hamlet@zulip.com")

        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)

        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], [])

    def test_json_list_add(self):
        # type: () -> None
        self.login("hamlet@zulip.com")

        result = self.client_put('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one ', '\n two', 'three'])})
        self.assert_json_success(result)

        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['one', 'two', 'three'])

    def test_json_list_remove(self):
        # type: () -> None
        self.login("hamlet@zulip.com")

        result = self.client_put('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)

        result = self.client_delete('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one'])})
        self.assert_json_success(result)

        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['two', 'three'])

    def test_json_list_set(self):
        # type: () -> None
        self.login("hamlet@zulip.com")

        result = self.client_put('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)

        result = self.client_post('/json/users/me/alert_words', {'alert_words': ujson.dumps(['a', 'b', 'c'])})
        self.assert_json_success(result)

        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['a', 'b', 'c'])

    def message_does_alert(self, user_profile, message):
        # type: (UserProfile, Text) -> bool
        """Send a bunch of messages as othello, so Hamlet is notified"""
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, message)
        user_message = most_recent_usermessage(user_profile)
        return 'has_alert_word' in user_message.flags_list()

    def test_alert_flags(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile_hamlet = self.example_user('hamlet')

        result = self.client_put('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)

        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['one', 'two', 'three'])

        # Alerts in the middle of messages work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Normal alert one time"))
        # Alerts at the end of messages work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Normal alert one"))
        # Alerts at the beginning of messages work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "two normal alerts"))
        # Alerts with surrounding punctuation work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "This one? should alert"))
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Definitely time for three."))
        # Multiple alerts in a message work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "One two three o'clock"))
        # Alerts are case-insensitive.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "One o'clock"))
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Case of ONE, won't stop me"))

        # We don't cause alerts for matches in URLs.
        self.assertFalse(self.message_does_alert(user_profile_hamlet, "Don't alert on http://t.co/one/ urls"))
        self.assertFalse(self.message_does_alert(user_profile_hamlet, "Don't alert on http://t.co/one urls"))

    def test_update_alert_words(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        me_email = user_profile.email

        self.login(me_email)
        result = self.client_put('/json/users/me/alert_words', {'alert_words': ujson.dumps(['ALERT'])})

        content = 'this is an ALERT for you'
        self.send_message(me_email, "Denmark", Recipient.STREAM, content)
        self.assert_json_success(result)

        original_message = most_recent_message(user_profile)

        user_message = most_recent_usermessage(user_profile)
        self.assertIn('has_alert_word', user_message.flags_list())

        result = self.client_patch("/json/messages/" + str(original_message.id), {
            'message_id': original_message.id,
            'content': 'new ALERT for you',
        })
        self.assert_json_success(result)

        user_message = most_recent_usermessage(user_profile)
        self.assertEqual(user_message.message.content, 'new ALERT for you')
        self.assertIn('has_alert_word', user_message.flags_list())

        result = self.client_patch("/json/messages/" + str(original_message.id), {
            'message_id': original_message.id,
            'content': 'sorry false alarm',
        })
        self.assert_json_success(result)

        user_message = most_recent_usermessage(user_profile)
        self.assertEqual(user_message.message.content, 'sorry false alarm')
        self.assertNotIn('has_alert_word', user_message.flags_list())
