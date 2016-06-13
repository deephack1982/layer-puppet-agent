#!/usr/bin/python3
# Copyright (c) 2016, James Beedy <jamesbeedy@gmail.com>

import os
import shutil

from charms import layer
from charms.reactive import when
from charms.reactive import when_not
from charms.reactive import set_state
from charms.reactive import when_any
from charms.reactive import when_none

from charmhelpers.core import hookenv

from charms.layer.puppet import PuppetConfigs
import charms.apt

config = hookenv.config()


@when('config.set.puppet-server')
@when_not('puppet-agent.installed')
def install_puppet_agent():
    '''Install puppet agent
    '''
    p = PuppetConfigs()
    # Download and install trusty puppet deb
    hookenv.status_set('maintenance',
                       'Installing puppet agent')
    p.install_puppet()
    p.puppet_active()
    set_state('puppet-agent.installed')


@when_not('config.set.puppet-server', 'puppet.available')
@when_not('apt.installed.puppet-common')
def masterless_puppet():
    '''Set the `puppet.available` state so that other layers can
    gate puppet operations for masterless puppet state (unconfigured)
    '''
    hookenv.status_set('maintenance',
                       'Configuring puppet repository')
    p = PuppetConfigs()
    # Configure puppet repo
    p.install_puppet_apt_src()
    charms.apt.queue_install(['puppet-common'])
    charms.apt.install_queued()
    hookenv.status_set('active',
                       'Masterless puppet configued')
    set_state('puppet.available')


@when_none('puppet-agent.installed', 'config.set.puppet-server')
@when('puppet.available', 'apt.installed.puppet-common')
def masterless_avail():
    cfg = layer.options('puppet-agent')
    if not cfg.get('silent'):
        hookenv.status_set('active',
                           'Masterless puppet configued')


@when('config.set.puppet-server')
@when_not('puppet-agent.configured', 'apt.queued_installs')
def configure_puppet_agent():
    '''Since the server is set we render
    the puppet config files and ensure puppet service running
    '''
    p = PuppetConfigs()
    p.configure_puppet()

    set_state('puppet-agent.configured')
    p.puppet_active()


@when('puppet-agent.installed', 'puppet-agent.configured')
@when_not('puppet-agent.available')
def puppet_agent_ready():

    '''
    Set the `puppet.masterfull.available` state to indicate puppet agent
    is installed, configured and started in master-client state.
    '''
    set_state('puppet-agent.available')


@when('config.changed.puppet-server', 'config.set.puppet-server')
def puppet_server_config_changed():

    '''React to puppet-server changed
    '''
    p = PuppetConfigs()
    if not config['ca-server']:
        if os.path.isdir(p.puppet_ssl_dir):
            shutil.rmtree(p.puppet_ssl_dir)
    p.render_puppet_conf()
    p.puppet_active()


@when('config.set.pin-puppet', 'config.changed.pin-puppet')
def puppet_version_config_changed():

    '''React to pin-puppet version changed
    '''
    p = PuppetConfigs()
    # Reinstall puppet to specified version
    hookenv.status_set('maintenance',
                       'Re-installing puppet.')
    if config.previous('pin-puppet') != config['pin-puppet'] and \
       (len(config['pin-puppet']) > 1):
        p.puppet_purge()
        p.install_puppet()
    p.puppet_active()


@when('config.set.puppet-server')
@when_any('config.changed.auto-start', 'config.changed.puppet-server')
def puppet_auto_start_config_changed():

    '''React to auto-start changed
    '''
    p = PuppetConfigs()
    hookenv.status_set('maintenance',
                       'Configuring auto-start')
    p.puppet_running()
    p.puppet_active()


@when('config.changed.environment', 'config.set.puppet-server')
def puppet_environment_config_changed():

    '''React to config-changed
    '''
    p = PuppetConfigs()
    hookenv.status_set('maintenance',
                       'Configuring new puppet env %s' % config['environment'])
    p.render_puppet_conf()
    p.puppet_active()


@when('config.changed.ca-server', 'config.set.puppet-server')
def puppet_ca_server_config_changed():

    '''React to config-changed
    '''
    p = PuppetConfigs()
    # Remove ssl dir if ca-server has changed to avoid
    # cert conflicts with pre-existing, now stale client
    # cert and new puppetmaster cert
    hookenv.status_set('maintenance',
                       'Reconfiguring puppet-agent for new ca-server.')
    if os.path.isdir(p.puppet_ssl_dir):
        shutil.rmtree(p.puppet_ssl_dir)
    p.render_puppet_conf()
    p.puppet_active()
