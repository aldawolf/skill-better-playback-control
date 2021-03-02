import random
from adapt.intent import IntentBuilder
from mycroft.skills.core import intent_handler
from mycroft.messagebus.message import Message
from ovos_utils.waiting_for_mycroft.base_skill import MycroftSkill
from ovos_utils.playback import CPSMatchType, CPSPlayback, CPSMatchConfidence,\
    BetterCommonPlayInterface, CPSTrackStatus
from ovos_utils.gui import is_gui_connected, GUIInterface


class BetterPlaybackControlSkill(MycroftSkill):

    def initialize(self):
        # TODO skill settings for these values
        self.cps = BetterCommonPlayInterface(bus=self.bus,
                                             max_timeout=3, min_timeout=1.5)
        self.prefer_gui = False  # not recommended
        self.ignore_gui = False
        # TODO remote_server support, ping @aix for details
        self.gui = GUIInterface(self.skill_id, bus=self.bus)

    def stop(self, message=None):
        # will stop any playback in GUI or AudioService
        return self.cps.stop()

    # play xxx intents
    @intent_handler("play.intent")
    def generic_play(self, message):
        self._play(message, CPSMatchType.GENERIC)

    @intent_handler("music.intent")
    def play_music(self, message):
        self._play(message, CPSMatchType.MUSIC)

    @intent_handler("video.intent")
    def play_video(self, message):
        self._play(message, CPSMatchType.VIDEO)

    @intent_handler("audiobook.intent")
    def play_audiobook(self, message):
        self._play(message, CPSMatchType.AUDIOBOOK)

    @intent_handler("game.intent")
    def play_game(self, message):
        self._play(message, CPSMatchType.GAME)

    @intent_handler("radio.intent")
    def play_radio(self, message):
        self._play(message, CPSMatchType.RADIO)

    @intent_handler("podcast.intent")
    def play_podcast(self, message):
        self._play(message, CPSMatchType.PODCAST)

    @intent_handler("news.intent")
    def play_news(self, message):
        self._play(message, CPSMatchType.NEWS)

    @intent_handler("tv.intent")
    def play_tv(self, message):
        self._play(message, CPSMatchType.TV)

    @intent_handler("movie.intent")
    def play_movie(self, message):
        self._play(message, CPSMatchType.MOVIE)

    @intent_handler("movietrailer.intent")
    def play_trailer(self, message):
        self._play(message, CPSMatchType.TRAILER)

    @intent_handler("porn.intent")
    def play_adult(self, message):
        self._play(message, CPSMatchType.ADULT)

    @intent_handler("comic.intent")
    def play_comic(self, message):
        self._play(message, CPSMatchType.VISUAL_STORY)

    # playback control intents
    @intent_handler(IntentBuilder('NextCommonPlay')
                    .require('Next').require("Playing").optionally("Track"))
    def handle_next(self, message):
        self.cps.play_next()

    @intent_handler(IntentBuilder('PrevCommonPlay')
                    .require('Prev').require("Playing").optionally("Track"))
    def handle_prev(self, message):
        self.cps.play_prev()

    @intent_handler(IntentBuilder('PauseCommonPlay')
                    .require('Pause').require("Playing"))
    def handle_pause(self, message):
        self.cps.pause()

    @intent_handler(IntentBuilder('ResumeCommonPlay')
                    .one_of('PlayResume', 'Resume').require("Playing"))
    def handle_resume(self, message):
        """Resume playback if paused"""
        self.cps.resume()

    # playback selection
    def should_resume(self, phrase):
        if self.cps.playback_status == CPSTrackStatus.PAUSED:
            if not phrase.strip() or \
                    self.voc_match(phrase, "Resume", exact=True) or \
                    self.voc_match(phrase, "Play", exact=True):
                return True
        return False

    def _play(self, message, media_type=CPSMatchType.GENERIC):
        phrase = message.data.get("query", "")

        # if media is currently paused, empty string means "resume playback"
        if self.should_resume(phrase):
            self.cps.resume()
            return

        self.speak_dialog("just.one.moment", wait=True)

        self.enclosure.mouth_think()

        # Now we place a query on the messsagebus for anyone who wants to
        # attempt to service a 'play.request' message.
        results = []
        for r in self.cps.search(phrase):
            results += r["results"]

        # filter GUI only results if GUI not connected
        gui_connected = is_gui_connected(self.bus)
        if self.ignore_gui or not gui_connected:
            results = [r for r in results if r["playback"] != CPSPlayback.GUI]

        if not results:
            self.speak_dialog("cant.play",
                              data={"phrase": search_phrase,
                                    "media_type": media_type})
            return

        # send all results for disambiguation
        # this can be used in GUI or any other use facing interface to
        # override the final selection
        for r in results:
            status = dict(r)
            status["status"] = CPSTrackStatus.DISAMBIGUATION
            self.bus.emit(Message('better_cps.status.update', status))

        best = self.select_best(results)
        self.enclosure.mouth_reset()
        self.set_context("Playing")
        self.cps.play(best)

    def select_best(self, results):
        # Look at any replies that arrived before the timeout
        # Find response(s) with the highest confidence
        best = None
        ties = []
        for handler in results:
            if not best or handler['match_confidence'] > best['match_confidence']:
                best = handler
                ties = [best]
            elif handler['match_confidence'] == best['match_confidence']:
                ties.append(handler)

        if ties:
            # select randomly
            selected = random.choice(ties)

            if self.prefer_gui:
                # select only from GUI results if preference is set
                # WARNING this can effectively make it so that the same
                # skill is always selected
                gui_results = [r for r in ties if r["playback"] ==
                               CPSPlayback.GUI]
                if len(gui_results):
                    selected = random.choice(gui_results)

            # TODO: Ask user to pick between ties or do it automagically
        else:
            selected = best

        return selected


def create_skill():
    return BetterPlaybackControlSkill()
