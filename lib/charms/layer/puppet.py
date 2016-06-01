#!/usr/bin/python3
# Copyright (c) 2016, James Beedy <jamesbeedy@gmail.com>

import os
from subprocess import call

from charmhelpers.core.templating import render
from charmhelpers.core import hookenv
from charmhelpers.core.host import lsb_release
from charmhelpers.fetch import (
    apt_install,
    apt_update,
    apt_hold,
)
from charmhelpers.fetch.archiveurl import (
    ArchiveUrlFetchHandler
)

config = hookenv.config()


class PuppetConfigs:
    def __init__(self):
        self.version = config['puppet-version']
        self.puppet_base_url = 'https://apt.puppetlabs.com'
        self.puppet_conf = 'puppet.conf'
        self.auto_start = ('yes', 'no')
        self.ensure_running = 'false'
        self.ubuntu_release = lsb_release()['DISTRIB_CODENAME']
        self.puppet_ssl_dir = '/var/lib/puppet/ssl/'
        self.puppet_pkg_vers = ''

        if config['puppet-version'] == 4:
            self.puppet_pkgs = ['puppet-agent']
            self.puppet_purge = ['puppet', 'puppet-common']
            if config['pin-puppet']:
                self.puppet_pkg_vers = \
                    [('puppet-agent=%s' % config['pin-puppet'])]
            else:
                self.puppet_pkg_vers = self.puppet_pkgs

            self.puppet_deb = 'puppetlabs-release-pc1-%s.deb' % \
                              self.ubuntu_release
            self.puppet_exe = '/opt/puppetlabs/bin/puppet'
            self.puppet_conf_dir = '/etc/puppetlabs/puppet'
            if config['auto-start']:
                self.ensure_running = 'true'
            self.enable_puppet_cmd = \
                ('%s resource service puppet ensure=running '
                 'enable=%s' % (self.puppet_exe, self.ensure_running))
        elif config['puppet-version'] == 3:
            self.puppet_pkgs = ['puppet', 'puppet-common']
            self.puppet_purge = ['puppet-agent']
            if config['pin-puppet']:
                self.puppet_pkg_vers = \
                    [('puppet=%s' % config['pin-puppet']),
                     ('puppet-common=%s' % config['pin-puppet'])]
            else:
                self.puppet_pkg_vers = self.puppet_pkgs
            self.puppet_deb = 'puppetlabs-release-%s.deb' % \
                self.ubuntu_release
            self.puppet_exe = '/usr/bin/puppet'
            self.puppet_conf_dir = '/etc/puppet'
            if config['auto-start']:
                self.auto_start = ('no', 'yes')
            self.enable_puppet_cmd = \
                ('sed -i /etc/default/puppet '
                 '-e s/START=%s/START=%s/' % self.auto_start)
        else:
            hookenv.log('Only puppet versions 3 and 4 suported')

        self.puppet_conf_ctxt = {
            'environment': config['environment'],
            'puppet_server': config['puppet-server']
        }
        if config['ca-server']:
            self.puppet_conf_ctxt['ca_server'] = config['ca-server']

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

    def puppet_deb_url(self):
        '''Return fully qualified puppet deb url
        '''
        puppet_deb_url = '%s/%s' % (self.puppet_base_url, self.puppet_deb)
        return puppet_deb_url

    def puppet_deb_temp(self):
        '''Return fully qualified path to downloaded deb
        '''
        puppet_deb_temp = os.path.join('/tmp', self.puppet_deb)
        return puppet_deb_temp

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

    def fetch_install_puppet_deb(self, puppet):
        '''Fetch and install the puppet deb
        '''
        hookenv.status_set('maintenance',
                           'Configuring Puppetlabs apt sources')
        aufh = ArchiveUrlFetchHandler()
        aufh.download(self.puppet_deb_url(), self.puppet_deb_temp())
        dpkg_puppet_deb = 'dpkg -i %s' % self.puppet_deb_temp()
        call(dpkg_puppet_deb.split(), shell=False)
        apt_update()

        # Clean up
        rm_trusty_puppet_deb = 'rm %s' % self.puppet_deb_temp()
        call(rm_trusty_puppet_deb.split(), shell=False)
        self.puppet_active()

    def install_puppet(self):
        '''Install puppet
        '''
        hookenv.status_set('maintenance',
                           'Installing puppet agent')
        self.fetch_install_puppet_deb(self)
        apt_install(self.puppet_pkg_vers)
        apt_hold(self.puppet_pkgs)

    def configure_puppet(self):
        '''Configure puppet
        '''
        hookenv.status_set('maintenance',
                           'Configuring puppet agent')
        self.render_puppet_conf()
        self.puppet_running()
        self.puppet_active()
