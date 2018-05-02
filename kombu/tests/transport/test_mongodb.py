from __future__ import absolute_import

from kombu import Connection

from kombu.tests.case import Case, SkipTest, Mock, skip_if_not_module


class MockConnection(dict):

    def __setattr__(self, key, value):
        self[key] = value


class test_mongodb(Case):

    def _get_connection(self, url, **kwargs):
        from kombu.transport import mongodb

        class _Channel(mongodb.Channel):

            def _create_client(self):
                self._client = Mock(name='client')

        class Transport(mongodb.Transport):
            Connection = MockConnection
            Channel = _Channel

        return Connection(url, transport=Transport, **kwargs).connect()

    @skip_if_not_module('pymongo')
    def test_defaults(self):
        url = 'mongodb://'

        c = self._get_connection(url)
        hostname, dbname, options = c.channels[0]._parse_uri()

        self.assertEqual(dbname, 'kombu_default')
        self.assertEqual(hostname, 'mongodb://127.0.0.1')

    @skip_if_not_module('pymongo')
    def test_custom_host(self):
        url = 'mongodb://localhost'
        c = self._get_connection(url)
        hostname, dbname, options = c.channels[0]._parse_uri()

        self.assertEqual(dbname, 'kombu_default')

    @skip_if_not_module('pymongo')
    def test_custom_database(self):
        url = 'mongodb://localhost/dbname'
        c = self._get_connection(url)
        hostname, dbname, options = c.channels[0]._parse_uri()

        self.assertEqual(dbname, 'dbname')

    @skip_if_not_module('pymongo')
    def test_custom_credentials(self):
        url = 'mongodb://localhost/dbname'
        c = self._get_connection(url, userid='foo', password='bar')
        hostname, dbname, options = c.channels[0]._parse_uri()

        self.assertEqual(hostname, 'mongodb://foo:bar@localhost/dbname')
        self.assertEqual(dbname, 'dbname')

    @skip_if_not_module('pymongo')
    def test_options(self):
        url = 'mongodb://localhost,localhost2:29017/dbname?fsync=true'
        c = self._get_connection(url)

        hostname, dbname, options = c.channels[0]._parse_uri()

        self.assertTrue(options['fsync'])

    @skip_if_not_module('pymongo')
    def test_srv(self):
        url = 'mongodb+srv://mongo.example.com/dbname?ssl=false'

        import pymongo.uri_parser
        c = self._get_connection(url)


        default_parser = pymongo.uri_parser.parse_uri

        def parse_uri(hostname, port):
            """Fake a parse_uri as if the proper SRV TXT and A records all
            exist

            Assumes a SRV record that points to mongo1 and mongo2.example.com
            at port 27017, a TXT record that sets the replicaSet to
            kombu-replica, and A records for both mongo1 and mongo2.
            """
            #The parse_uri method calls out to DNS, so mock it.

            return {
                'username': None,
                'nodelist': [
                    ('mongo1.example.com', 27017),
                    ('mongo2.example.com', 27017)
                ],
                'database': 'dbname',
                'collection': None,
                'password': None,
                'options': {
                    'ssl': False,
                    'replicaset': u'kombu-replica'
                }
            }

        pymongo.uri_parser.parse_uri = parse_uri
        try:
            hostname, dbname, options = c.channels[0]._parse_uri()
            self.assertEqual(hostname, url)
            self.assertEqual(dbname, 'dbname')
            self.assertEqual(options.get('ssl', None), False)
        finally:
            pymongo.uri_parser.parse_uri = default_parser


    @skip_if_not_module('pymongo')
    def test_real_connections(self):
        from pymongo.errors import ConfigurationError

        raise SkipTest(
            'Test is functional: it actually connects to mongod')

        url = 'mongodb://localhost,localhost:29017/dbname'
        c = self._get_connection(url)
        client = c.channels[0].client

        nodes = client.connection.nodes
        # If there's just 1 node it is because we're  connecting to a single
        # server instead of a repl / mongoss.
        if len(nodes) == 2:
            self.assertTrue(('localhost', 29017) in nodes)
            self.assertEqual(client.name, 'dbname')

        url = 'mongodb://localhost:27017,localhost2:29017/dbname'
        c = self._get_connection(url)
        client = c.channels[0].client

        # Login to admin db since there's no db specified
        url = 'mongodb://adminusername:adminpassword@localhost'
        c = self._get_connection()
        client = c.channels[0].client
        self.assertEqual(client.name, 'kombu_default')

        # Lets make sure that using admin db doesn't break anything
        # when no user is specified
        url = 'mongodb://localhost'
        c = self._get_connection(url)
        client = c.channels[0].client

        # Assuming there's user 'username' with password 'password'
        # configured in mongodb
        url = 'mongodb://username:password@localhost/dbname'
        c = self._get_connection(url)
        client = c.channels[0].client

        # Assuming there's no user 'nousername' with password 'nopassword'
        # configured in mongodb
        url = 'mongodb://nousername:nopassword@localhost/dbname'
        c = self._get_connection(url)

        with self.assertRaises(ConfigurationError):
            c.channels[0].client
