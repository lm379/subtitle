# -*- coding: utf-8 -*-

# The original author of this program, Danmaku2ASS, is StarBrilliant.
# This file is released under General Public License version 3.
# You should have received a copy of General Public License text alongside with
# this program. If not, you can obtain it at http://gnu.org/copyleft/gpl.html .
# This program comes with no warranty, the author will not be resopnsible for
# any damage or problems caused by this program.

# You can obtain a latest copy of Danmaku2ASS at:
#   https://github.com/m13253/danmaku2ass
# Please update to the latest version before complaining.

import io
import json
import logging
import math
import random
import re
import xml.dom.minidom


def SeekZero(function):
    def decorated_function(file_):
        file_.seek(0)
        try:
            return function(file_)
        finally:
            file_.seek(0)
    return decorated_function


def EOFAsNone(function):
    def decorated_function(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except EOFError:
            return None
    return decorated_function


@SeekZero
@EOFAsNone
def ProbeCommentFormat(f):
    tmp = f.read(1)
    if tmp == '[':
        return 'Acfun'
        # It is unwise to wrap a JSON object in an array!
        # See this: http://haacked.com/archive/2008/11/20/anatomy-of-a-subtle-json-vulnerability.aspx/
        # Do never follow what Acfun developers did!
    elif tmp == '{':
        tmp = f.read(14)
        if tmp == '"status_code":':
            return 'Tudou'
        elif tmp.strip().startswith('"result'):
            return 'Tudou2'
    elif tmp == '<':
        tmp = f.read(1)
        if tmp == '?':
            tmp = f.read(38)
            if tmp == 'xml version="1.0" encoding="UTF-8"?><p':
                return 'Niconico'
            elif tmp == 'xml version="1.0" encoding="UTF-8"?><i':
                return 'Bilibili'
            elif tmp == 'xml version="2.0" encoding="UTF-8"?><i':
                return 'Bilibili2'
            elif tmp == 'xml version="1.0" encoding="utf-8"?><i':
                return 'Bilibili'  # tucao.cc, with the same file format as Bilibili
            elif tmp == 'xml version="1.0" encoding="Utf-8"?>\n<':
                return 'Bilibili'  # Komica, with the same file format as Bilibili
            elif tmp == 'xml version="1.0" encoding="UTF-8"?>\n<':
                tmp = f.read(20)
                if tmp == '!-- BoonSutazioData=':
                    return 'Niconico'  # Niconico videos downloaded with NicoFox
                else:
                    return 'MioMio'
        elif tmp == 'p':
            return 'Niconico'  # Himawari Douga, with the same file format as Niconico Douga


# Result: (f, dx, dy)
# To convert: NewX = f*x+dx, NewY = f*y+dy
def GetZoomFactor(SourceSize, TargetSize):
    try:
        if (SourceSize, TargetSize) == GetZoomFactor.Cached_Size:
            return GetZoomFactor.Cached_Result
    except AttributeError:
        pass
    GetZoomFactor.Cached_Size = (SourceSize, TargetSize)
    try:
        SourceAspect = SourceSize[0] / SourceSize[1]
        TargetAspect = TargetSize[0] / TargetSize[1]
        if TargetAspect < SourceAspect:  # narrower
            ScaleFactor = TargetSize[0] / SourceSize[0]
            GetZoomFactor.Cached_Result = (
                ScaleFactor, 0, (TargetSize[1] - TargetSize[0] / SourceAspect) / 2)
        elif TargetAspect > SourceAspect:  # wider
            ScaleFactor = TargetSize[1] / SourceSize[1]
            GetZoomFactor.Cached_Result = (
                ScaleFactor, (TargetSize[0] - TargetSize[1] * SourceAspect) / 2, 0)
        else:
            GetZoomFactor.Cached_Result = (TargetSize[0] / SourceSize[0], 0, 0)
        return GetZoomFactor.Cached_Result
    except ZeroDivisionError:
        GetZoomFactor.Cached_Result = (1, 0, 0)
        return GetZoomFactor.Cached_Result


# Calculation is based on https://github.com/jabbany/CommentCoreLibrary/issues/5#issuecomment-40087282
#                     and https://github.com/m13253/danmaku2ass/issues/7#issuecomment-41489422
# ASS FOV = width*4/3.0
# But Flash FOV = width/math.tan(100*math.pi/360.0)/2 will be used instead
# Result: (transX, transY, rotX, rotY, rotZ, scaleX, scaleY)
def ConvertFlashRotation(rotY, rotZ, X, Y, width, height):
    def WrapAngle(deg):
        return 180 - ((180 - deg) % 360)
    rotY = WrapAngle(rotY)
    rotZ = WrapAngle(rotZ)
    if rotY in (90, -90):
        rotY -= 1
    if rotY == 0 or rotZ == 0:
        outX = 0
        outY = -rotY  # Positive value means clockwise in Flash
        outZ = -rotZ
        rotY *= math.pi / 180.0
        rotZ *= math.pi / 180.0
    else:
        rotY *= math.pi / 180.0
        rotZ *= math.pi / 180.0
        outY = math.atan2(-math.sin(rotY) * math.cos(rotZ),
                          math.cos(rotY)) * 180 / math.pi
        outZ = math.atan2(-math.cos(rotY) * math.sin(rotZ),
                          math.cos(rotZ)) * 180 / math.pi
        outX = math.asin(math.sin(rotY) * math.sin(rotZ)) * 180 / math.pi
    trX = (X * math.cos(rotZ) + Y * math.sin(rotZ)) / math.cos(rotY) + (1 - math.cos(rotZ) /
                                                                        math.cos(rotY)) * width / 2 - math.sin(rotZ) / math.cos(rotY) * height / 2
    trY = Y * math.cos(rotZ) - X * math.sin(rotZ) + math.sin(rotZ) * \
        width / 2 + (1 - math.cos(rotZ)) * height / 2
    trZ = (trX - width / 2) * math.sin(rotY)
    FOV = width * math.tan(2 * math.pi / 9.0) / 2
    try:
        scaleXY = FOV / (FOV + trZ)
    except ZeroDivisionError:
        logging.error(
            'Rotation makes object behind the camera: trZ == %.0f' % trZ)
        scaleXY = 1
    trX = (trX - width / 2) * scaleXY + width / 2
    trY = (trY - height / 2) * scaleXY + height / 2
    if scaleXY < 0:
        scaleXY = -scaleXY
        outX += 180
        outY += 180
        logging.error(
            'Rotation makes object behind the camera: trZ == %.0f < %.0f' % (trZ, FOV))
    return (trX, trY, WrapAngle(outX), WrapAngle(outY), WrapAngle(outZ), scaleXY * 100, scaleXY * 100)


def TestFreeRows(rows, c, row, width, height, bottomReserved, duration_marquee, duration_still):
    res = 0
    rowmax = height - bottomReserved
    targetRow = None
    if c[4] in (1, 2):
        while row < rowmax and res < c[7]:
            if targetRow != rows[c[4]][row]:
                targetRow = rows[c[4]][row]
                if targetRow and targetRow[0] + duration_still > c[0]:
                    break
            row += 1
            res += 1
    else:
        try:
            thresholdTime = c[0] - duration_marquee * \
                (1 - width / (c[8] + width))
        except ZeroDivisionError:
            thresholdTime = c[0] - duration_marquee
        while row < rowmax and res < c[7]:
            if targetRow != rows[c[4]][row]:
                targetRow = rows[c[4]][row]
                try:
                    if targetRow and (targetRow[0] > thresholdTime or targetRow[0] + targetRow[8] * duration_marquee / (targetRow[8] + width) > c[0]):
                        break
                except ZeroDivisionError:
                    pass
            row += 1
            res += 1
    return res


def FindAlternativeRow(rows, c, height, bottomReserved):
    res = 0
    for row in range(height - bottomReserved - math.ceil(c[7])):
        if not rows[c[4]][row]:
            return row
        elif rows[c[4]][row][0] < rows[c[4]][res][0]:
            res = row
    return res


def MarkCommentRow(rows, c, row):
    try:
        for i in range(row, row + math.ceil(c[7])):
            rows[c[4]][i] = c
    except IndexError:
        pass


def ASSEscape(s):
    def ReplaceLeadingSpace(s):
        if len(s) == 0:
            return s
        if s[0] in (' ', '\t'):
            s = '\u200b' + s
        if s[-1] in (' ', '\t'):
            s = s + '\u200b'
        return s
    return '\\N'.join((ReplaceLeadingSpace(i) or ' ' for i in str(s).replace('\\', '\\\u200b').replace('{', '\\{').replace('}', '\\}').split('\n')))


def CalculateLength(s):
    return max(map(len, s.split('\n')))  # May not be accurate


def ConvertTimestamp(timestamp):
    timestamp = round(timestamp * 100.0)
    hour, minute = divmod(timestamp, 360000)
    minute, second = divmod(minute, 6000)
    second, centsecond = divmod(second, 100)
    return '%d:%02d:%02d.%02d' % (int(hour), int(minute), int(second), int(centsecond))


def ConvertColor(RGB, width=1280, height=576):
    if RGB == 0x000000:
        return '000000'
    elif RGB == 0xffffff:
        return 'FFFFFF'
    R = (RGB >> 16) & 0xff
    G = (RGB >> 8) & 0xff
    B = RGB & 0xff
    if width < 1280 and height < 576:
        return '%02X%02X%02X' % (B, G, R)
    else:  # VobSub always uses BT.601 colorspace, convert to BT.709
        def ClipByte(x): return 255 if x > 255 else 0 if x < 0 else round(x)
        return '%02X%02X%02X' % (
            ClipByte(R * 0.00956384088080656 + G *
                     0.03217254540203729 + B * 0.95826361371715607),
            ClipByte(R * -0.10493933142075390 + G *
                     1.17231478191855154 + B * -0.06737545049779757),
            ClipByte(R * 0.91348912373987645 + G *
                     0.07858536372532510 + B * 0.00792551253479842)
        )


def ConvertType2(row, height, bottomReserved):
    return height - bottomReserved - row


def ConvertToFile(filename_or_file, *args, **kwargs):
    if isinstance(filename_or_file, bytes):
        filename_or_file = str(
            bytes(filename_or_file).decode('utf-8', 'replace'))
    if isinstance(filename_or_file, str):
        return open(filename_or_file, *args, **kwargs)
    else:
        return filename_or_file


def FilterBadChars(f):
    s = f.read()
    s = re.sub('[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]', '\ufffd', s)
    return io.StringIO(s)


class safe_list(list):

    def get(self, index, default=None):
        try:
            return self[index]
        except IndexError:
            return default


class BilibiliDanmaku(object):
    def __init__(self, xml, width=1920, height=1080, protect=0, font='sans-serif', fontsize=25.0, alpha=1.0, duration_marquee=5.0, duration_still=5.0,is_reduce_comments=False) -> None:
        self.xml = re.sub('[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]', '\ufffd', xml)
        self.width = width
        self.height = height
        self.font = font
        self.fontsize = fontsize
        self.protect = protect
        self.alpha = alpha
        self.duration_marquee = duration_marquee
        self.duration_still = duration_still
        self.is_reduce_comments = is_reduce_comments
        self.text_opacity = 1.0

        self.ass = ""

    def ReadCommentsBilibili1(self):
        dom = xml.dom.minidom.parseString(self.xml)
        comment_element = dom.getElementsByTagName('d')
        for i, comment in enumerate(comment_element):
            try:
                p = str(comment.getAttribute('p')).split(',')
                assert len(p) >= 5
                assert p[1] in ('1', '4', '5', '6', '7', '8')
                if comment.childNodes.length > 0:
                    if p[1] in ('1', '4', '5', '6'):
                        c = str(comment.childNodes[0].wholeText).replace(
                            '/n', '\n')
                        size = int(p[2]) * self.fontsize / 25.0
                        yield (float(p[0]), int(p[4]), i, c, {'1': 0, '4': 2, '5': 1, '6': 3}[p[1]], int(p[3]), size, (c.count('\n') + 1) * size, CalculateLength(c) * size)
                    elif p[1] == '7':  # positioned comment
                        c = str(comment.childNodes[0].wholeText)
                        yield (float(p[0]), int(p[4]), i, c, 'bilipos', int(p[3]), int(p[2]), 0, 0)
                    elif p[1] == '8':
                        pass  # ignore scripted comment
            except (AssertionError, AttributeError, IndexError, TypeError, ValueError):
                logging.warning(_('Invalid comment: %s') % comment.toxml())
                continue

    def ReadCommentsBilibili2(self):
        dom = xml.dom.minidom.parseString(self.xml)
        comment_element = dom.getElementsByTagName('d')
        for i, comment in enumerate(comment_element):
            try:
                p = str(comment.getAttribute('p')).split(',')
                assert len(p) >= 7
                assert p[3] in ('1', '4', '5', '6', '7', '8')
                if comment.childNodes.length > 0:
                    time = float(p[2]) / 1000.0
                    if p[3] in ('1', '4', '5', '6'):
                        c = str(comment.childNodes[0].wholeText).replace(
                            '/n', '\n')
                        size = int(p[4]) * self.fontsize / 25.0
                        yield (time, int(p[6]), i, c, {'1': 0, '4': 2, '5': 1, '6': 3}[p[3]], int(p[5]), size, (c.count('\n') + 1) * size, CalculateLength(c) * size)
                    elif p[3] == '7':  # positioned comment
                        c = str(comment.childNodes[0].wholeText)
                        yield (time, int(p[6]), i, c, 'bilipos', int(p[5]), int(p[4]), 0, 0)
                    elif p[3] == '8':
                        pass  # ignore scripted comment
            except (AssertionError, AttributeError, IndexError, TypeError, ValueError):
                logging.warning(_('Invalid comment: %s') % comment.toxml())
                continue

    def WriteCommentBilibiliPositioned(self, c, width, height, styleid):
        # BiliPlayerSize = (512, 384)  # Bilibili player version 2010
        # BiliPlayerSize = (540, 384)  # Bilibili player version 2012
        BiliPlayerSize = (672, 438)  # Bilibili player version 2014
        ZoomFactor = GetZoomFactor(BiliPlayerSize, (width, height))

        def GetPosition(InputPos, isHeight):
            isHeight = int(isHeight)  # True -> 1
            if isinstance(InputPos, int):
                return ZoomFactor[0] * InputPos + ZoomFactor[isHeight + 1]
            elif isinstance(InputPos, float):
                if InputPos > 1:
                    return ZoomFactor[0] * InputPos + ZoomFactor[isHeight + 1]
                else:
                    return BiliPlayerSize[isHeight] * ZoomFactor[0] * InputPos + ZoomFactor[isHeight + 1]
            else:
                try:
                    InputPos = int(InputPos)
                except ValueError:
                    InputPos = float(InputPos)
                return GetPosition(InputPos, isHeight)

        try:
            comment_args = safe_list(json.loads(c[3]))
            text = ASSEscape(str(comment_args[4]).replace('/n', '\n'))
            from_x = comment_args.get(0, 0)
            from_y = comment_args.get(1, 0)
            to_x = comment_args.get(7, from_x)
            to_y = comment_args.get(8, from_y)
            from_x = GetPosition(from_x, False)
            from_y = GetPosition(from_y, True)
            to_x = GetPosition(to_x, False)
            to_y = GetPosition(to_y, True)
            alpha = safe_list(str(comment_args.get(2, '1')).split('-'))
            from_alpha = float(alpha.get(0, 1))
            to_alpha = float(alpha.get(1, from_alpha))
            from_alpha = 255 - round(from_alpha * 255)
            to_alpha = 255 - round(to_alpha * 255)
            rotate_z = int(comment_args.get(5, 0))
            rotate_y = int(comment_args.get(6, 0))
            lifetime = float(comment_args.get(3, 4500))
            duration = int(comment_args.get(9, lifetime * 1000))
            delay = int(comment_args.get(10, 0))
            fontface = comment_args.get(12)
            isborder = comment_args.get(11, 'true')
            from_rotarg = ConvertFlashRotation(
                rotate_y, rotate_z, from_x, from_y, width, height)
            to_rotarg = ConvertFlashRotation(
                rotate_y, rotate_z, to_x, to_y, width, height)
            styles = ['\\org(%d, %d)' % (width / 2, height / 2)]
            if from_rotarg[0:2] == to_rotarg[0:2]:
                styles.append('\\pos(%.0f, %.0f)' % (from_rotarg[0:2]))
            else:
                styles.append('\\move(%.0f, %.0f, %.0f, %.0f, %.0f, %.0f)' % (
                    from_rotarg[0:2] + to_rotarg[0:2] + (delay, delay + duration)))
            styles.append(
                '\\frx%.0f\\fry%.0f\\frz%.0f\\fscx%.0f\\fscy%.0f' % (from_rotarg[2:7]))
            if (from_x, from_y) != (to_x, to_y):
                styles.append('\\t(%d, %d, ' % (delay, delay + duration))
                styles.append(
                    '\\frx%.0f\\fry%.0f\\frz%.0f\\fscx%.0f\\fscy%.0f' % (to_rotarg[2:7]))
                styles.append(')')
            if fontface:
                styles.append('\\fn%s' % ASSEscape(fontface))
            styles.append('\\fs%.0f' % (c[6] * ZoomFactor[0]))
            if c[5] != 0xffffff:
                styles.append('\\c&H%s&' % ConvertColor(c[5]))
                if c[5] == 0x000000:
                    styles.append('\\3c&HFFFFFF&')
            if from_alpha == to_alpha:
                styles.append('\\alpha&H%02X' % from_alpha)
            elif (from_alpha, to_alpha) == (255, 0):
                styles.append('\\fad(%.0f,0)' % (lifetime * 1000))
            elif (from_alpha, to_alpha) == (0, 255):
                styles.append('\\fad(0, %.0f)' % (lifetime * 1000))
            else:
                styles.append('\\fade(%(from_alpha)d, %(to_alpha)d, %(to_alpha)d, 0, %(end_time).0f, %(end_time).0f, %(end_time).0f)' % {
                              'from_alpha': from_alpha, 'to_alpha': to_alpha, 'end_time': lifetime * 1000})
            if isborder == 'false':
                styles.append('\\bord0')
            self.ass += 'Dialogue: -1,%(start)s,%(end)s,%(styleid)s,,0,0,0,,{%(styles)s}%(text)s\n' % {'start': ConvertTimestamp(
                c[0]), 'end': ConvertTimestamp(c[0] + lifetime), 'styles': ''.join(styles), 'text': text, 'styleid': styleid}
            # f.write('Dialogue: -1,%(start)s,%(end)s,%(styleid)s,,0,0,0,,{%(styles)s}%(text)s\n' % {'start': ConvertTimestamp(c[0]), 'end': ConvertTimestamp(c[0] + lifetime), 'styles': ''.join(styles), 'text': text, 'styleid': styleid})
        except (IndexError, ValueError) as e:
            try:
                logging.warning(_('Invalid comment: %r') % c[3])
            except IndexError:
                logging.warning(_('Invalid comment: %r') % c)

    def WriteCommentAcfunPositioned(self, c, width, height, styleid):
        AcfunPlayerSize = (560, 400)
        ZoomFactor = GetZoomFactor(AcfunPlayerSize, (width, height))

        def GetPosition(InputPos, isHeight):
            isHeight = int(isHeight)  # True -> 1
            return AcfunPlayerSize[isHeight] * ZoomFactor[0] * InputPos * 0.001 + ZoomFactor[isHeight + 1]

        def GetTransformStyles(x=None, y=None, scale_x=None, scale_y=None, rotate_z=None, rotate_y=None, color=None, alpha=None):
            styles = []
            out_x, out_y = x, y
            if rotate_z is not None and rotate_y is not None:
                assert x is not None
                assert y is not None
                rotarg = ConvertFlashRotation(
                    rotate_y, rotate_z, x, y, width, height)
                out_x, out_y = rotarg[0:2]
                if scale_x is None:
                    scale_x = 1
                if scale_y is None:
                    scale_y = 1
                styles.append('\\frx%.0f\\fry%.0f\\frz%.0f\\fscx%.0f\\fscy%.0f' % (
                    rotarg[2:5] + (rotarg[5] * scale_x, rotarg[6] * scale_y)))
            else:
                if scale_x is not None:
                    styles.append('\\fscx%.0f' % (scale_x * 100))
                if scale_y is not None:
                    styles.append('\\fscy%.0f' % (scale_y * 100))
            if color is not None:
                styles.append('\\c&H%s&' % ConvertColor(color))
                if color == 0x000000:
                    styles.append('\\3c&HFFFFFF&')
            if alpha is not None:
                alpha = 255 - round(alpha * 255)
                styles.append('\\alpha&H%02X' % alpha)
            return out_x, out_y, styles

        def FlushCommentLine(text, styles, start_time, end_time, styleid):
            if end_time > start_time:
                self.ass += 'Dialogue: -1,%(start)s,%(end)s,%(styleid)s,,0,0,0,,{%(styles)s}%(text)s\n' % {'start': ConvertTimestamp(
                    start_time), 'end': ConvertTimestamp(end_time), 'styles': ''.join(styles), 'text': text, 'styleid': styleid}

        try:
            comment_args = c[3]
            text = ASSEscape(str(comment_args['n']).replace('\r', '\n'))
            common_styles = ['\org(%d, %d)' % (width / 2, height / 2)]
            anchor = {0: 7, 1: 8, 2: 9, 3: 4, 4: 5, 5: 6, 6: 1,
                      7: 2, 8: 3}.get(comment_args.get('c', 0), 7)
            if anchor != 7:
                common_styles.append('\\an%s' % anchor)
            font = comment_args.get('w')
            if font:
                font = dict(font)
                fontface = font.get('f')
                if fontface:
                    common_styles.append('\\fn%s' % ASSEscape(str(fontface)))
                fontbold = bool(font.get('b'))
                if fontbold:
                    common_styles.append('\\b1')
            common_styles.append('\\fs%.0f' % (c[6] * ZoomFactor[0]))
            isborder = bool(comment_args.get('b', True))
            if not isborder:
                common_styles.append('\\bord0')
            to_pos = dict(comment_args.get('p', {'x': 0, 'y': 0}))
            to_x = round(GetPosition(int(to_pos.get('x', 0)), False))
            to_y = round(GetPosition(int(to_pos.get('y', 0)), True))
            to_scale_x = float(comment_args.get('e', 1.0))
            to_scale_y = float(comment_args.get('f', 1.0))
            to_rotate_z = float(comment_args.get('r', 0.0))
            to_rotate_y = float(comment_args.get('k', 0.0))
            to_color = c[5]
            to_alpha = float(comment_args.get('a', 1.0))
            from_time = float(comment_args.get('t', 0.0))
            action_time = float(comment_args.get('l', 3.0))
            actions = list(comment_args.get('z', []))
            to_out_x, to_out_y, transform_styles = GetTransformStyles(
                to_x, to_y, to_scale_x, to_scale_y, to_rotate_z, to_rotate_y, to_color, to_alpha)
            self.FlushCommentLine(text, common_styles + ['\\pos(%.0f, %.0f)' % (
                to_out_x, to_out_y)] + transform_styles, c[0] + from_time, c[0] + from_time + action_time, styleid)
            action_styles = transform_styles
            for action in actions:
                action = dict(action)
                from_x, from_y = to_x, to_y
                from_out_x, from_out_y = to_out_x, to_out_y
                from_scale_x, from_scale_y = to_scale_x, to_scale_y
                from_rotate_z, from_rotate_y = to_rotate_z, to_rotate_y
                from_color, from_alpha = to_color, to_alpha
                transform_styles, action_styles = action_styles, []
                from_time += action_time
                action_time = float(action.get('l', 0.0))
                if 'x' in action:
                    to_x = round(GetPosition(int(action['x']), False))
                if 'y' in action:
                    to_y = round(GetPosition(int(action['y']), True))
                if 'f' in action:
                    to_scale_x = float(action['f'])
                if 'g' in action:
                    to_scale_y = float(action['g'])
                if 'c' in action:
                    to_color = int(action['c'])
                if 't' in action:
                    to_alpha = float(action['t'])
                if 'd' in action:
                    to_rotate_z = float(action['d'])
                if 'e' in action:
                    to_rotate_y = float(action['e'])
                to_out_x, to_out_y, action_styles = GetTransformStyles(
                    to_x, to_y, from_scale_x, from_scale_y, to_rotate_z, to_rotate_y, from_color, from_alpha)
                if (from_out_x, from_out_y) == (to_out_x, to_out_y):
                    pos_style = '\\pos(%.0f, %.0f)' % (to_out_x, to_out_y)
                else:
                    pos_style = '\\move(%.0f, %.0f, %.0f, %.0f)' % (
                        from_out_x, from_out_y, to_out_x, to_out_y)
                styles = common_styles + transform_styles
                styles.append(pos_style)
                if action_styles:
                    styles.append('\\t(%s)' % (''.join(action_styles)))
                self.FlushCommentLine(
                    text, styles, c[0] + from_time, c[0] + from_time + action_time, styleid)
        except (IndexError, ValueError) as e:
            logging.warning(_('Invalid comment: %r') % c[3])

    def ProcessComments(self, comments, width, height, bottomReserved, fontface, fontsize, alpha, duration_marquee, duration_still, filters_regex=[], reduced=False, progress_callback=None):
        styleid = 'Danmaku2ASS_%04x' % random.randint(0, 0xffff)
        self.WriteASSHead(width, height, fontface, fontsize, alpha, styleid)
        rows = [[None] * (height - bottomReserved + 1) for i in range(4)]
        for idx, i in enumerate(comments):
            if progress_callback and idx % 1000 == 0:
                progress_callback(idx, len(comments))
            if isinstance(i[4], int):
                skip = False
                for filter_regex in filters_regex:
                    if filter_regex and filter_regex.search(i[3]):
                        skip = True
                        break
                if skip:
                    continue
                row = 0
                rowmax = height - bottomReserved - i[7]
                while row <= rowmax:
                    freerows = TestFreeRows(
                        rows, i, row, width, height, bottomReserved, duration_marquee, duration_still)
                    if freerows >= i[7]:
                        MarkCommentRow(rows, i, row)
                        self.WriteComment(i, row, width, height, bottomReserved,
                                          fontsize, duration_marquee, duration_still, styleid)
                        break
                    else:
                        row += freerows or 1
                else:
                    if not reduced:
                        row = FindAlternativeRow(
                            rows, i, height, bottomReserved)
                        MarkCommentRow(rows, i, row)
                        self.WriteComment(i, row, width, height, bottomReserved,
                                          fontsize, duration_marquee, duration_still, styleid)
            elif i[4] == 'bilipos':
                self.WriteCommentBilibiliPositioned(i, width, height, styleid)
            elif i[4] == 'acfunpos':
                self.WriteCommentAcfunPositioned(i, width, height, styleid)
            else:
                logging.warning(_('Invalid comment: %r') % i[3])
        if progress_callback:
            progress_callback(len(comments), len(comments))

    def WriteASSHead(self, width, height, fontface, fontsize, alpha, styleid):
        self.ass += '''[Script Info]
    ; Script generated by Danmaku2ASS
    ; https://github.com/m13253/danmaku2ass
    Script Updated By: Danmaku2ASS (https://github.com/m13253/danmaku2ass)
    ScriptType: v4.00+
    PlayResX: %(width)d
    PlayResY: %(height)d
    Aspect Ratio: %(width)d:%(height)d
    Collisions: Normal
    WrapStyle: 2
    ScaledBorderAndShadow: yes
    YCbCr Matrix: TV.601

    [V4+ Styles]
    Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    Style: %(styleid)s, %(fontface)s, %(fontsize).0f, &H%(alpha)02XFFFFFF, &H%(alpha)02XFFFFFF, &H%(alpha)02X000000, &H%(alpha)02X000000, 0, 0, 0, 0, 100, 100, 0.00, 0.00, 1, %(outline).0f, 0, 7, 0, 0, 0, 0

    [Events]
    Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
    ''' % {'width': width, 'height': height, 'fontface': fontface, 'fontsize': fontsize, 'alpha': 255 - round(alpha * 255), 'outline': max(fontsize / 25.0, 1), 'styleid': styleid}

    def WriteComment(self, c, row, width, height, bottomReserved, fontsize, duration_marquee, duration_still, styleid):
        text = ASSEscape(c[3])
        styles = []
        if c[4] == 1:
            styles.append('\\an8\\pos(%(halfwidth)d, %(row)d)' %
                          {'halfwidth': width / 2, 'row': row})
            duration = duration_still
        elif c[4] == 2:
            styles.append('\\an2\\pos(%(halfwidth)d, %(row)d)' % {
                          'halfwidth': width / 2, 'row': ConvertType2(row, height, bottomReserved)})
            duration = duration_still
        elif c[4] == 3:
            styles.append('\\move(%(neglen)d, %(row)d, %(width)d, %(row)d)' % {
                          'width': width, 'row': row, 'neglen': -math.ceil(c[8])})
            duration = duration_marquee
        else:
            styles.append('\\move(%(width)d, %(row)d, %(neglen)d, %(row)d)' % {
                          'width': width, 'row': row, 'neglen': -math.ceil(c[8])})
            duration = duration_marquee
        if not (-1 < c[6] - fontsize < 1):
            styles.append('\\fs%.0f' % c[6])
        if c[5] != 0xffffff:
            styles.append('\\c&H%s&' % ConvertColor(c[5]))
            if c[5] == 0x000000:
                styles.append('\\3c&HFFFFFF&')
        self.ass += 'Dialogue: 2,%(start)s,%(end)s,%(styleid)s,,0000,0000,0000,,{%(styles)s}%(text)s\n' % {'start': ConvertTimestamp(
            c[0]), 'end': ConvertTimestamp(c[0] + duration), 'styles': ''.join(styles), 'text': text, 'styleid': styleid}

    def toAss(self):
        comments = []
        if '<?xml version="1.0"' in self.xml:
            comments.extend(self.ReadCommentsBilibili1())
        elif '<?xml version="2.0"' in self.xml:
            comments.extend(self.ReadCommentsBilibili2())
        else:
            return

        self.ProcessComments(comments, self.width, self.height, self.protect, self.font,
                             self.fontsize, self.alpha, self.duration_marquee, self.duration_still,reduced=self.is_reduce_comments)
        return self.ass