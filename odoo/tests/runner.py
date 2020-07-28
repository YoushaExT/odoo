import logging
import unittest

# backwards compatibility
_logger = logging.getLogger('odoo.modules.module')
class OdooTestResult(unittest.result.TestResult):
    """
    This class in inspired from TextTestResult (https://github.com/python/cpython/blob/master/Lib/unittest/runner.py)
    Instead of using a stream, we are using the logger,
    but replacing the "findCaller" in order to give the information we
    have based on the test object that is running.
    """
    def __str__(self):
        return f'{len(self.failures)} failed, {len(self.errors)} errors of {self.testsRun} tests'

    def update(self, other):
        """ Merges an other test result into this one, only updates contents

        :type other: OdooTestResult
        """
        self.failures.extend(other.failures)
        self.errors.extend(other.errors)
        self.testsRun += other.testsRun
        self.skipped.extend(other.skipped)
        self.expectedFailures.extend(other.expectedFailures)
        self.unexpectedSuccesses.extend(other.unexpectedSuccesses)
        self.shouldStop = self.shouldStop or other.shouldStop

    def log(self, level, msg, *args, test=None, exc_info=None, extra=None, stack_info=False, caller_infos=None):
        """
        ``test`` is the running test case, ``caller_infos`` is
        (fn, lno, func, sinfo) (logger.findCaller format), see logger.log for
        the other parameters.
        """
        test = test or self
        if isinstance(test, unittest.case._SubTest) and test.test_case:
            test = test.test_case
        logger = logging.getLogger(test.__module__)
        try:
            caller_infos = caller_infos or logger.findCaller(stack_info)
        except ValueError:
            caller_infos = "(unknown file)", 0, "(unknown function)", None
        (fn, lno, func, sinfo) = caller_infos
        # using logger.log makes it difficult to spot-replace findCaller in
        # order to provide useful location information (the problematic spot
        # inside the test function), so use lower-level functions instead
        if logger.isEnabledFor(level):
            record = logger.makeRecord(logger.name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)
            logger.handle(record)

    def getDescription(self, test):
        if isinstance(test, unittest.case._SubTest):
            return 'Subtest %s' % test._subDescription()
        if isinstance(test, unittest.TestCase):
            # since we have the module name in the logger, this will avoid to duplicate module info in log line
            # we only apply this for TestCase since we can receive error handler or other special case
            return "%s.%s" % (test.__class__.__qualname__, test._testMethodName)
        return str(test)

    def startTest(self, test):
        super().startTest(test)
        self.log(logging.INFO, 'Starting %s ...', self.getDescription(test), test=test)

    def addError(self, test, err):
        super().addError(test, err)
        self.logError("ERROR", test, err)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.logError("FAIL", test, err)

    def addSubTest(self, test, subtest, err):
        # since addSubTest is not making a call to addFailure or addError we need to manage it too
        # https://github.com/python/cpython/blob/3.7/Lib/unittest/result.py#L136
        if err is not None:
            if issubclass(err[0], test.failureException):
                flavour = "FAIL"
            else:
                flavour = "ERROR"
            self.logError(flavour, subtest, err)
        super().addSubTest(test, subtest, err)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.log(logging.INFO, 'skipped %s', self.getDescription(test), test=test)

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.log(logging.ERROR, 'unexpected success for %s', self.getDescription(test), test=test)

    def logError(self, flavour, test, error):
        err = self._exc_info_to_string(error, test)
        caller_infos = self.getErrorCallerInfo(error, test)
        self.log(logging.INFO, '=' * 70, test=test, caller_infos=caller_infos)  # keep this as info !!!!!!
        self.log(logging.ERROR, "%s: %s\n%s", flavour, self.getDescription(test), err, test=test, caller_infos=caller_infos)

    def getErrorCallerInfo(self, error, test):
        """
        :param error: A tuple (exctype, value, tb) as returned by sys.exc_info().
        :param test: A TestCase that created this error.
        :returns: a tuple (fn, lno, func, sinfo) matching the logger findCaller format or None
        """

        # only test case should be executed in odoo, this is only a safe guard
        if isinstance(test, unittest.suite._ErrorHolder):
            return
        if not isinstance(test, unittest.TestCase):
            _logger.warning('%r is not a TestCase' % test)
            return
        _, _, error_traceback = error

        while error_traceback:
            code = error_traceback.tb_frame.f_code
            if code.co_name == test._testMethodName:
                lineno = error_traceback.tb_lineno
                filename = code.co_filename
                method = test._testMethodName
                infos = (filename, lineno, method, None)
                return infos
            error_traceback = error_traceback.tb_next


class OdooTestRunner(object):
    """A test runner class that displays results in in logger using OdooTestResult.
    Simplified verison of TextTestRunner
    """

    def run(self, test):
        result = OdooTestResult()
        test(result)
        return result
