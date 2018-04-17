# coding=utf-8
"""
Unit/functional testing for ply based parsing in cmd2

Todo List
- multiline
- unicode
- case sensitive flag
- figure out how to let users change the terminator character

Notes:

- Shortcuts may have to be discarded, or handled in a different way than they
  are with pyparsing.
- valid comment styles:
    - C-style -> /* comment */
    - C++-style -> // comment
    - Python/Shell style -> # comment

"""

import re
import shlex

import pytest

class Cmd2Command():
    pass

class Cmd2Parser():
    def parseString(self, rawinput):
        result = Cmd2Command()
        result.raw = rawinput
        result.command = None
        result.args = None
        result.terminator = None
        result.suffix = None
        result.pipeTo = None
        result.output = None
        result.outputTo = None

        # in theory we let people change this
        terminator = ';'

        # strip C-style and C++-style comments
        # shlex will handle the python/shell style comments for us
        def replacer(match):
                s = match.group(0)
                if s.startswith('/'):
                    # treat the removed comment as a space token, not an empty string
                    # return ' '
                    # jk, always return nothing
                    return ''
                else:
                    return s
        pattern = re.compile(
            r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
            re.DOTALL | re.MULTILINE
        )
        rawinput = re.sub(pattern, replacer, rawinput)

        s = shlex.shlex(rawinput, posix=False)
        s.whitespace_split = True
        tokens = self.split_on_punctuation(list(s))
        
        # look for the semicolon terminator
        try:
            terminator_pos = tokens.index(terminator)
            # everything before the first terminator is the command and the args
            (result.command, result.args) = self._command_and_args(tokens[:terminator_pos])
            result.terminator = tokens[terminator_pos]
            # we will set the suffix later
            # remove all the tokens before and including the terminator
            tokens = tokens[terminator_pos+1:]
        except ValueError:
            # no terminator in the tokens
            pass

        # check for output redirect
        try:
            output_pos = tokens.index('>')
            result.output = '>'
            result.outputTo = ' '.join(tokens[output_pos+1:])
            # remove all the tokens after the output redirect
            tokens = tokens[:output_pos]
        except ValueError:
            pass

        # check for pipes
        try:
            # find the first pipe if it exists
            pipe_pos = tokens.index('|')
            # set everything after the first pipe to result.pipeTo
            result.pipeTo = ' '.join(tokens[pipe_pos+1:])
            # remove all the tokens after the pipe
            tokens = tokens[:pipe_pos]
        except ValueError:
            # no pipe in the tokens
            pass
        
        if result.terminator:
            # whatever is left is the suffix
            result.suffix = ' '.join(tokens)
        else:
            # no terminator, so whatever is left is the command and the args
            (result.command, result.args) = self._command_and_args(tokens)            

        return result
    
    def _command_and_args(self, tokens):
        """given a list of tokens, and return a tuple of the command
        and the args as a string.
        """
        command = None
        args = None

        if tokens:
            command = tokens[0]

        if len(tokens) > 1:
            args = ' '.join(tokens[1:])

        return (command, args)

    def split_on_punctuation(self, initial_tokens):
        """
        # Further splits tokens from a command line using punctuation characters
        # as word breaks when they are in unquoted strings. Each run of punctuation
        # characters is treated as a single token.

        :param initial_tokens: the tokens as parsed by shlex
        :return: the punctuated tokens
        """
        punctuation = [';'] # should be self.terminator from cmd2.py
        if True:  # should be self.allow_redirection from cmd2.py
            punctuation += ['|', '<', '>'] # should be REDIRECTION_CHARS from cmd2.py

        punctuated_tokens = []

        for cur_initial_token in initial_tokens:

            # Save tokens up to 1 character in length or quoted tokens. No need to parse these.
            if len(cur_initial_token) <= 1 or cur_initial_token[0] in ['"', "'"]: # should be QUOTES in cmd2.py
                punctuated_tokens.append(cur_initial_token)
                continue

            # Iterate over each character in this token
            cur_index = 0
            cur_char = cur_initial_token[cur_index]

            # Keep track of the token we are building
            new_token = ''

            while True:
                if cur_char not in punctuation:

                    # Keep appending to new_token until we hit a punctuation char
                    while cur_char not in punctuation:
                        new_token += cur_char
                        cur_index += 1
                        if cur_index < len(cur_initial_token):
                            cur_char = cur_initial_token[cur_index]
                        else:
                            break

                else:
                    cur_punc = cur_char

                    # Keep appending to new_token until we hit something other than cur_punc
                    while cur_char == cur_punc:
                        new_token += cur_char
                        cur_index += 1
                        if cur_index < len(cur_initial_token):
                            cur_char = cur_initial_token[cur_index]
                        else:
                            break

                # Save the new token
                punctuated_tokens.append(new_token)
                new_token = ''

                # Check if we've viewed all characters
                if cur_index >= len(cur_initial_token):
                    break

        return punctuated_tokens

@pytest.fixture
def parser():
    parser = Cmd2Parser()
    return parser

@pytest.mark.parametrize('tokens,command,args', [
    ( [], None, None),
    ( ['command'], 'command', None ),
    ( ['command', 'arg1', 'arg2'], 'command', 'arg1 arg2')
])
def test_command_and_args(parser, tokens, command, args):
    (parsed_command, parsed_args) = parser._command_and_args(tokens)
    assert command == parsed_command
    assert args == parsed_args

@pytest.mark.parametrize('line', [
    'plainword',
    '"one word"',
    "'one word'",
])
def test_single_word(parser, line):
    results = parser.parseString(line)
    assert results.command == line

def test_word_plus_terminator(parser):
    line = 'termbare;'
    results = parser.parseString(line)
    assert results.command == 'termbare'
    assert results.terminator == ';'

def test_suffix_after_terminator(parser):
    line = 'termbare; suffx'
    results = parser.parseString(line)
    assert results.command == 'termbare'
    assert results.terminator == ';'
    assert results.suffix == 'suffx'

def test_command_with_args(parser):
    line = 'command with args'
    results = parser.parseString(line)
    assert results.command == 'command'
    assert results.args == 'with args'
    assert not results.pipeTo

def test_hashcomment(parser):
    results = parser.parseString('hi # this is all a comment')
    assert results.command == 'hi'
    assert not results.args
    assert not results.pipeTo

def test_c_comment(parser):
    results = parser.parseString('hi /* this is | all a comment */')
    assert results.command == 'hi'
    assert not results.args
    assert not results.pipeTo

def test_c_comment_empty(parser):
    results = parser.parseString('/* this is | all a comment */')
    assert not results.command
    assert not results.args
    assert not results.pipeTo

def test_parse_what_if_quoted_strings_seem_to_start_comments(parser):
    results = parser.parseString('what if "quoted strings /* seem to " start comments?')
    assert results.command == 'what'
    assert results.args == 'if "quoted strings /* seem to " start comments?'
    assert not results.pipeTo

def test_cpp_comment(parser):
    results = parser.parseString('hi // this is | all a comment */')
    assert results.command == 'hi'
    assert not results.args
    assert not results.pipeTo

def test_simple_piped(parser):
    results = parser.parseString('simple | piped')
    assert results.command == 'simple'
    assert not results.args
    assert results.pipeTo == 'piped'

def test_double_pipe_is_not_a_pipe(parser):
    line = 'double-pipe || is not a pipe'
    results = parser.parseString(line)
    assert results.command == 'double-pipe'
    assert results.args == '|| is not a pipe'
    assert not results.pipeTo

def test_complex_pipe(parser):
    line = 'command with args, terminator;sufx | piped'
    results = parser.parseString(line)
    assert results.command == 'command'
    assert results.args == "with args, terminator"
    assert results.terminator == ';'
    assert results.suffix == 'sufx'
    assert results.pipeTo == 'piped'

def test_output_redirect(parser):
    line = 'output into > afile.txt'
    results = parser.parseString(line)
    assert results.command == 'output'
    assert results.args == 'into'
    assert results.output == '>'
    assert results.outputTo == 'afile.txt'

def test_output_redirect_with_dash_in_path(parser):
    line = 'output into > python-cmd2/afile.txt'
    results = parser.parseString(line)
    assert results.command == 'output'
    assert results.args == 'into'
    assert results.output == '>'
    assert results.outputTo == 'python-cmd2/afile.txt'

def test_pipe_and_redirect(parser):
    line = 'output into;sufx | pipethrume plz > afile.txt'
    results = parser.parseString(line)
    assert results.command == 'output'
    assert results.args == 'into'
    assert results.terminator == ';'
    assert results.suffix == 'sufx'
    assert results.pipeTo == 'pipethrume plz'
    assert results.output == '>'
    assert results.outputTo == 'afile.txt'

def test_has_redirect_inside_terminator(parser):
    """The terminator designates the end of the commmand/arguments portion.  If a redirector
    occurs before a terminator, then it will be treated as part of the arguments and not as a redirector."""
    line = 'has > inside;'
    results = parser.parseString(line)
    assert results.command == 'has'
    assert results.args == '> inside'
    assert results.terminator == ';'
def test_parse_command_with_unicode_args(parser):
    line = 'drink café'
    results = parser.parseString(line)
    assert results.command == 'drink'
    assert results.args == 'café'

def test_parse_unicode_command(parser):
    line = 'café au lait'
    results = parser.parseString(line)
    assert results.command == 'café'
    assert results.args == 'au lait'

def test_parse_redirect_to_unicode_filename(parser):
    line = 'dir home > café'
    results = parser.parseString(line)
    assert results.command == 'dir'
    assert results.args == 'home'
    assert results.output == '>'
    assert results.outputTo == 'café'

