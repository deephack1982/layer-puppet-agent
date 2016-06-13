#!/usr/bin/python3
# Copyright (c) 2016, James Beedy <jamesbeedy@gmail.com>

import os
from subprocess import call

from charms import layer
from charmhelpers.core.templating import render
from charmhelpers.core import hookenv
from charmhelpers.core.host import lsb_release

import charms.apt


config = hookenv.config()


class PuppetConfigs:
    def __init__(self):
        self.options = layer.options('puppet-agent')
        self.version = self.options.get('puppet-version')
        self.puppet_base_url = 'http://apt.puppetlabs.com'
        self.puppet_conf = 'puppet.conf'
        self.auto_start = ('yes', 'no')
        self.ensure_running = 'false'
        self.ubuntu_release = lsb_release()['DISTRIB_CODENAME']
        self.puppet_ssl_dir = '/var/lib/puppet/ssl/'
        self.puppet_pkg_vers = ''
        self.puppet_gpg_key = config['puppet-gpg-key']

        if self.version == '4':
            self.puppet_pkgs = ['puppet-agent']
            self.puppet_purge_pkgs = ['puppet', 'puppet-common']
            if config['pin-puppet']:
                self.puppet_pkg_vers = \
                    [('puppet-agent=%s' % config['pin-puppet'])]
            else:
                self.puppet_pkg_vers = self.puppet_pkgs

            self.puppet_exe = '/opt/puppetlabs/bin/puppet'
            self.puppet_conf_dir = '/etc/puppetlabs/puppet'
            self.puppet_apt_src = 'deb %s %s PC1' % \
                                  (self.puppet_base_url, self.ubuntu_release)
            if config['auto-start']:
                self.ensure_running = 'true'
            self.enable_puppet_cmd = \
                ('%s resource service puppet ensure=running '
                 'enable=%s' % (self.puppet_exe, self.ensure_running))
        elif self.version == '3':
            self.puppet_pkgs = ['puppet', 'puppet-common']
            self.puppet_purge_pkgs = ['puppet-agent']
            if config['pin-puppet']:
                self.puppet_pkg_vers = \
                    [('puppet=%s' % config['pin-puppet']),
                     ('puppet-common=%s' % config['pin-puppet'])]
            else:
                self.puppet_pkg_vers = self.puppet_pkgs
            self.puppet_exe = '/usr/bin/puppet'
            self.puppet_conf_dir = '/etc/puppet'
            self.puppet_apt_src = 'deb %s %s main dependencies' % \
                                  (self.puppet_base_url, self.ubuntu_release)
            if config['auto-start']:
                self.auto_start = ('no', 'yes')
            self.enable_puppet_cmd = \
                ('sed -i /etc/default/puppet '
                 '-e s/START=%s/START=%s/' % self.auto_start)
        else:
            hookenv.status_set('blocked',
                               'Only puppet versions 3 and 4 suported')

        self.puppet_conf_ctxt = {
            'environment': config['environment'],
            'puppet_server': config['puppet-server']
        }
        if config['ca-server']:
            self.puppet_conf_ctxt['ca_server'] = config['ca-server']

    def puppet_purge(self):
        ''' Purge appropriate puppet pkgs
        '''
        hookenv.status_set('maintenance',
                           'Purging puppet pkgs')
        if self.puppet_purge_pkgs in charms.apt.installed():
            charms.apt.purge(self.puppet_purge_pkgs)

    def render_puppet_conf(self):
        ''' Render puppet.conf
        '''
        if os.path.exists(self.puppet_conf_path()):
            os.remove(self.puppet_conf_path())
        render(source=self.puppet_conf,
               target=self.puppet_conf_path(),
               owner='root',
               perms=0o644,
               context=self.puppet_conf_ctxt)

    def puppet_conf_path(self):
        '''Return fully qualified path to puppet.conf
        '''
        puppet_conf_path = '%s/%s' % (self.puppet_conf_dir, self.puppet_conf)
        return puppet_conf_path

    def puppet_running(self):

        '''Enable or disable puppet auto-start
        '''
        call(self.enable_puppet_cmd.split(), shell=False)

    def puppet_active(self):
        if config['auto-start']:
            hookenv.status_set('active',
                               'Puppet-agent running')
        else:
            hookenv.status_set('active',
                               'Puppet-agent installed, but not running')

    def install_puppet_apt_src(self):
        '''Fetch and install the puppet gpg key and puppet deb source
        '''
        hookenv.status_set('maintenance',
                           'Configuring Puppetlabs apt sources')
        # Add puppet gpg id and apt source
        charms.apt.add_source(self.puppet_apt_src, key=self.puppet_gpg_key)
        # Apt update to pick up the sources
        charms.apt.update()

    def install_puppet(self):
        '''Install puppet
        '''
        hookenv.status_set('maintenance',
                           'Installing puppet agent')
        self.install_puppet_apt_src()
        # Queue the installation of appropriate puppet pkgs
        charms.apt.queue_install(self.puppet_pkg_vers)
        charms.apt.install_queued()

    def configure_puppet(self):
        '''Configure puppet
        '''
        hookenv.status_set('maintenance',
                           'Configuring puppet agent')
        self.render_puppet_conf()
        self.puppet_running()
