"""Read-only AMQP authentication probes: never publish, consume or declare."""
from urllib.parse import urlsplit, urlunsplit


class BrokerProbeError(RuntimeError):
    pass


def verify_logins(urls, forbidden_vhost):
    from amqp.exceptions import NotAllowed
    from kombu import Connection
    if set(urls) != {"api", "worker", "scheduler"}:
        raise BrokerProbeError("three_broker_roles_required")
    for role, url in urls.items():
        try:
            endpoint = urlsplit(url)
            if endpoint.path == "/" + forbidden_vhost or not forbidden_vhost:
                raise BrokerProbeError("distinct_negative_vhost_required")
            with Connection(url, connect_timeout=3, transport_options={"read_timeout": 3, "write_timeout": 3}) as connection:
                connection.ensure_connection(max_retries=0)
                connection.channel().close()
            other = urlunsplit(endpoint._replace(path="/" + forbidden_vhost))
            try:
                with Connection(other, connect_timeout=3) as connection:
                    connection.ensure_connection(max_retries=0)
            except NotAllowed:
                pass
            else:
                raise BrokerProbeError("broker_foreign_vhost_not_denied")
        except BrokerProbeError:
            raise
        except Exception:
            # URLs/passwords can be present in client exception strings.
            raise BrokerProbeError("broker_authentication_probe_failed") from None
    return {"authenticated_roles": 3, "foreign_vhost_denied": 3, "messages_touched": False}
